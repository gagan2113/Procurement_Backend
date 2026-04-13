from sqlalchemy import inspect, text
from pathlib import Path

from backend.db.session import engine
from backend.db.session import SessionLocal
from backend.db.base import Base
from backend.db.vendor_seed import ensure_vendor_seed_data
from backend.utils.logger import get_logger

# Import all models so they are registered on the Base metadata
import backend.models.bid  # noqa: F401
import backend.models.request  # noqa: F401
import backend.models.rfq  # noqa: F401
import backend.models.vendor  # noqa: F401

logger = get_logger(__name__)


def _sync_purchase_request_schema() -> None:
    """Patch table schema drift for SQLite without dropping existing data."""
    table_name = "purchase_requests"
    inspector = inspect(engine)

    if table_name not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns(table_name)}

    with engine.begin() as conn:
        if "expected_delivery_date" not in columns:
            conn.execute(text(
                "ALTER TABLE purchase_requests ADD COLUMN expected_delivery_date DATE"
            ))
            conn.execute(text(
                """
                UPDATE purchase_requests
                SET expected_delivery_date = DATE('now', '+30 day')
                WHERE expected_delivery_date IS NULL
                """
            ))
            logger.info("Schema migration: added expected_delivery_date column")

        # Normalize legacy values like "YYYY-MM-DD HH:MM:SS" to date-only format.
        conn.execute(text(
            """
            UPDATE purchase_requests
            SET expected_delivery_date = DATE(expected_delivery_date)
            WHERE expected_delivery_date IS NOT NULL
            """
        ))

        # Backfill any unparseable/empty values to keep ORM Date loading stable.
        conn.execute(text(
            """
            UPDATE purchase_requests
            SET expected_delivery_date = DATE('now', '+30 day')
            WHERE expected_delivery_date IS NULL OR TRIM(expected_delivery_date) = ''
            """
        ))


def _sync_rfq_schema() -> None:
    """Patch RFQ table schema drift for SQLite without dropping existing data."""
    table_name = "rfqs"
    inspector = inspect(engine)

    if table_name not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns(table_name)}

    with engine.begin() as conn:
        if "category" not in columns:
            conn.execute(text(
                "ALTER TABLE rfqs ADD COLUMN category VARCHAR(120)"
            ))
            logger.info("Schema migration: added category column to rfqs")

        if "pdf_path" not in columns:
            conn.execute(text(
                "ALTER TABLE rfqs ADD COLUMN pdf_path VARCHAR(512)"
            ))
            logger.info("Schema migration: added pdf_path column to rfqs")

        if "invited_vendors_count" not in columns:
            conn.execute(text(
                "ALTER TABLE rfqs ADD COLUMN invited_vendors_count INTEGER DEFAULT 0"
            ))
            conn.execute(text(
                "UPDATE rfqs SET invited_vendors_count = 0 WHERE invited_vendors_count IS NULL"
            ))
            logger.info("Schema migration: added invited_vendors_count column to rfqs")

        if "last_sent_at" not in columns:
            conn.execute(text(
                "ALTER TABLE rfqs ADD COLUMN last_sent_at DATETIME"
            ))
            logger.info("Schema migration: added last_sent_at column to rfqs")


def _sync_bid_schema() -> None:
    """Patch quotation/evaluation schema drift for SQLite without dropping existing data."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if "quotations" not in tables:
        return

    quotation_columns = {col["name"] for col in inspector.get_columns("quotations")}

    with engine.begin() as conn:
        if "price" not in quotation_columns:
            conn.execute(text("ALTER TABLE quotations ADD COLUMN price FLOAT"))
        if "lead_time_days" not in quotation_columns:
            conn.execute(text("ALTER TABLE quotations ADD COLUMN lead_time_days INTEGER"))
        if "delivery_schedule" not in quotation_columns:
            conn.execute(text("ALTER TABLE quotations ADD COLUMN delivery_schedule TEXT"))
        if "delivery_terms" not in quotation_columns:
            conn.execute(text("ALTER TABLE quotations ADD COLUMN delivery_terms TEXT"))
        if "payment_terms" not in quotation_columns:
            conn.execute(text("ALTER TABLE quotations ADD COLUMN payment_terms TEXT"))
        if "validity_days" not in quotation_columns:
            conn.execute(text("ALTER TABLE quotations ADD COLUMN validity_days INTEGER"))
        if "specification_compliance" not in quotation_columns:
            conn.execute(text("ALTER TABLE quotations ADD COLUMN specification_compliance FLOAT"))
        if "alternative_product" not in quotation_columns:
            conn.execute(text("ALTER TABLE quotations ADD COLUMN alternative_product TEXT"))
        if "quotation_pdf_path" not in quotation_columns:
            conn.execute(text("ALTER TABLE quotations ADD COLUMN quotation_pdf_path VARCHAR(512)"))
        if "technical_sheet_path" not in quotation_columns:
            conn.execute(text("ALTER TABLE quotations ADD COLUMN technical_sheet_path VARCHAR(512)"))
        if "compliance_documents_path" not in quotation_columns:
            conn.execute(text("ALTER TABLE quotations ADD COLUMN compliance_documents_path VARCHAR(512)"))
        if "certifications_path" not in quotation_columns:
            conn.execute(text("ALTER TABLE quotations ADD COLUMN certifications_path VARCHAR(512)"))
        if "document_status" not in quotation_columns:
            conn.execute(text("ALTER TABLE quotations ADD COLUMN document_status VARCHAR(20) DEFAULT 'pending'"))
        if "extracted_price" not in quotation_columns:
            conn.execute(text("ALTER TABLE quotations ADD COLUMN extracted_price FLOAT"))
        if "extracted_delivery_terms" not in quotation_columns:
            conn.execute(text("ALTER TABLE quotations ADD COLUMN extracted_delivery_terms TEXT"))
        if "extracted_conditions" not in quotation_columns:
            conn.execute(text("ALTER TABLE quotations ADD COLUMN extracted_conditions TEXT"))
        if "extracted_compliance_details" not in quotation_columns:
            conn.execute(text("ALTER TABLE quotations ADD COLUMN extracted_compliance_details TEXT"))
        if "document_summary" not in quotation_columns:
            conn.execute(text("ALTER TABLE quotations ADD COLUMN document_summary TEXT"))
        if "document_compliance_score" not in quotation_columns:
            conn.execute(text("ALTER TABLE quotations ADD COLUMN document_compliance_score FLOAT"))

        # Backfill core fields for any legacy rows where new columns are null.
        conn.execute(text(
            """
            UPDATE quotations
            SET
                price = COALESCE(price, 0),
                lead_time_days = COALESCE(lead_time_days, 1),
                delivery_schedule = COALESCE(delivery_schedule, ''),
                delivery_terms = COALESCE(delivery_terms, ''),
                payment_terms = COALESCE(payment_terms, ''),
                validity_days = COALESCE(validity_days, 30),
                specification_compliance = COALESCE(specification_compliance, 0),
                document_status = COALESCE(document_status, 'pending')
            """
        ))

        # One-time migration path from old bids table if data exists and quotations is empty.
        if "bids" in tables:
            legacy_count = conn.execute(text("SELECT COUNT(1) FROM bids")).scalar() or 0
            quotation_count = conn.execute(text("SELECT COUNT(1) FROM quotations")).scalar() or 0
            if legacy_count > 0 and quotation_count == 0:
                conn.execute(text(
                    """
                    INSERT INTO quotations (
                        id,
                        rfq_id,
                        vendor_id,
                        vendor_name,
                        price,
                        currency,
                        lead_time_days,
                        delivery_schedule,
                        delivery_terms,
                        payment_terms,
                        validity_days,
                        specification_compliance,
                        alternative_product,
                        status,
                        normalized_price,
                        normalized_delivery,
                        normalized_quality,
                        normalization_meta,
                        created_at,
                        updated_at,
                        document_status
                    )
                    SELECT
                        id,
                        rfq_id,
                        vendor_id,
                        vendor_name,
                        COALESCE(quoted_price, 0),
                        COALESCE(currency, 'INR'),
                        COALESCE(quoted_delivery_days, 1),
                        COALESCE(notes, ''),
                        COALESCE(notes, ''),
                        COALESCE(CAST(payment_terms_days AS TEXT), ''),
                        30,
                        COALESCE(technical_compliance_pct, 0),
                        NULL,
                        COALESCE(status, 'submitted'),
                        normalized_price,
                        normalized_delivery,
                        normalized_quality,
                        normalization_meta,
                        created_at,
                        updated_at,
                        'pending'
                    FROM bids
                    """
                ))
                logger.info("Schema migration: migrated legacy bids data into quotations")

    if "bid_evaluations" not in tables:
        return

    evaluation_columns = {col["name"] for col in inspector.get_columns("bid_evaluations")}
    with engine.begin() as conn:
        if "reliability_score" not in evaluation_columns:
            conn.execute(text("ALTER TABLE bid_evaluations ADD COLUMN reliability_score FLOAT"))
        if "capability_score" not in evaluation_columns:
            conn.execute(text("ALTER TABLE bid_evaluations ADD COLUMN capability_score FLOAT"))
        if "document_compliance_score" not in evaluation_columns:
            conn.execute(text("ALTER TABLE bid_evaluations ADD COLUMN document_compliance_score FLOAT"))
        if "manual_override" not in evaluation_columns:
            conn.execute(text("ALTER TABLE bid_evaluations ADD COLUMN manual_override BOOLEAN DEFAULT 0"))
        if "score_breakdown" not in evaluation_columns:
            conn.execute(text("ALTER TABLE bid_evaluations ADD COLUMN score_breakdown JSON"))


def create_all_tables() -> None:
    """Create all database tables and patch schema drift for SQLite."""
    Base.metadata.create_all(bind=engine)
    _sync_purchase_request_schema()
    _sync_rfq_schema()
    _sync_bid_schema()

    workbook_path = Path(__file__).resolve().parents[2] / "VendorDatabase_ProcureAI.xlsx"
    with SessionLocal() as db:
        seeded = ensure_vendor_seed_data(db=db, excel_path=workbook_path)
        if seeded:
            logger.info("Vendor seed data loaded from %s", workbook_path)
