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


def create_all_tables() -> None:
    """Create all database tables and patch schema drift for SQLite."""
    Base.metadata.create_all(bind=engine)
    _sync_purchase_request_schema()
    _sync_rfq_schema()

    workbook_path = Path(__file__).resolve().parents[2] / "VendorDatabase_ProcureAI.xlsx"
    with SessionLocal() as db:
        seeded = ensure_vendor_seed_data(db=db, excel_path=workbook_path)
        if seeded:
            logger.info("Vendor seed data loaded from %s", workbook_path)
