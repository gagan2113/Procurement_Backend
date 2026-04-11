from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import openpyxl
from sqlalchemy.orm import Session

from backend.models.vendor import Contract, MaterialVendorMap, PurchaseHistory, Vendor, VendorPerformance
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_bool(value: Any) -> bool:
    text = (_clean_text(value) or "").upper()
    return text in {"YES", "Y", "TRUE", "1"}


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = _clean_text(value)
    if not text:
        return None

    text = (
        text.replace(",", "")
        .replace("%", "")
        .replace("\u20b9", "")
        .replace("$", "")
        .strip()
    )
    try:
        return float(text)
    except ValueError:
        return None


def _to_int(value: Any) -> int | None:
    as_float = _to_float(value)
    if as_float is None:
        return None
    return int(as_float)


def _to_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = _clean_text(value)
    if not text:
        return None

    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _iter_data_rows(sheet) -> Any:
    # Row 1 is sheet title and row 2 is header in this workbook format.
    for row in sheet.iter_rows(min_row=3, values_only=True):
        yield row


def seed_vendor_tables_from_excel(db: Session, excel_path: Path) -> int:
    """Load vendor domain data from workbook into normalized SQLite tables."""
    if not excel_path.exists():
        logger.warning("Vendor seed file not found at %s", excel_path)
        return 0

    workbook = openpyxl.load_workbook(excel_path, data_only=True)

    vendors_sheet = workbook["Vendor Master"]
    deals_sheet = workbook["Past Deals"]
    performance_sheet = workbook["Performance Scorecard"]
    contracts_sheet = workbook["Contract Register"]
    material_map_sheet = workbook["Material-Vendor Map"]

    db.query(PurchaseHistory).delete()
    db.query(VendorPerformance).delete()
    db.query(Contract).delete()
    db.query(MaterialVendorMap).delete()
    db.query(Vendor).delete()

    inserted_vendors = 0

    for row in _iter_data_rows(vendors_sheet):
        vendor_id = _clean_text(row[0])
        if not vendor_id:
            continue

        db.add(
            Vendor(
                vendor_id=vendor_id,
                vendor_name=_clean_text(row[1]) or "Unknown Vendor",
                category=_clean_text(row[2]),
                sub_category=_clean_text(row[3]),
                gstin=_clean_text(row[4]),
                pan=_clean_text(row[5]),
                city=_clean_text(row[6]),
                state=_clean_text(row[7]),
                country=_clean_text(row[8]),
                contact_person=_clean_text(row[9]),
                phone=_clean_text(row[10]),
                email=_clean_text(row[11]),
                contract_exists=_to_bool(row[12]),
                contract_id=_clean_text(row[13]),
                contract_valid_until=_to_date(row[14]),
                sap_vendor_code=_clean_text(row[15]),
                payment_terms_days=_to_int(row[16]),
                currency=_clean_text(row[17]),
            )
        )
        inserted_vendors += 1

    for row in _iter_data_rows(deals_sheet):
        deal_id = _clean_text(row[0])
        vendor_id = _clean_text(row[1])
        if not deal_id or not vendor_id:
            continue

        db.add(
            PurchaseHistory(
                deal_id=deal_id,
                vendor_id=vendor_id,
                vendor_name=_clean_text(row[2]),
                po_number=_clean_text(row[3]),
                category=_clean_text(row[4]),
                material_or_service=_clean_text(row[5]),
                quantity=_to_float(row[6]),
                unit=_clean_text(row[7]),
                unit_price=_to_float(row[8]),
                total_value=_to_float(row[9]),
                po_date=_to_date(row[10]),
                delivery_date=_to_date(row[11]),
                actual_delivery=_to_date(row[12]),
                status=_clean_text(row[13]),
            )
        )

    for row in _iter_data_rows(performance_sheet):
        vendor_id = _clean_text(row[0])
        if not vendor_id:
            continue

        db.add(
            VendorPerformance(
                vendor_id=vendor_id,
                vendor_name=_clean_text(row[1]),
                category=_clean_text(row[2]),
                on_time_delivery_pct=_to_float(row[3]),
                quality_score=_to_float(row[4]),
                price_competitiveness=_to_float(row[5]),
                defect_rate_pct=_to_float(row[6]),
                response_time_hours=_to_float(row[7]),
                compliance_score=_to_float(row[8]),
                total_orders=_to_int(row[9]),
                completed_orders=_to_int(row[10]),
                disputes_raised=_to_int(row[11]),
                avg_delay_days=_to_float(row[12]),
                risk_level=_clean_text(row[13]),
                ai_score=_to_float(row[14]),
            )
        )

    for row in _iter_data_rows(contracts_sheet):
        contract_id = _clean_text(row[0])
        vendor_id = _clean_text(row[1])
        if not contract_id or not vendor_id:
            continue

        db.add(
            Contract(
                contract_id=contract_id,
                vendor_id=vendor_id,
                vendor_name=_clean_text(row[2]),
                category=_clean_text(row[3]),
                contract_type=_clean_text(row[4]),
                start_date=_to_date(row[5]),
                end_date=_to_date(row[6]),
                contract_value=_to_float(row[7]),
                negotiated_rate=_clean_text(row[8]),
                sla_terms=_clean_text(row[9]),
                payment_terms=_clean_text(row[10]),
                auto_renew=_to_bool(row[11]),
                status=_clean_text(row[12]),
            )
        )

    for row in _iter_data_rows(material_map_sheet):
        material_code = _clean_text(row[0])
        if not material_code:
            continue

        db.add(
            MaterialVendorMap(
                material_code=material_code,
                material_description=_clean_text(row[1]),
                category=_clean_text(row[2]),
                primary_vendor_id=_clean_text(row[3]),
                primary_vendor=_clean_text(row[4]),
                secondary_vendor_id=_clean_text(row[5]),
                secondary_vendor=_clean_text(row[6]),
                contract_available=_to_bool(row[7]),
                preferred_vendor_id=_clean_text(row[8]),
            )
        )

    db.commit()
    logger.info("Seeded vendor tables from workbook: %s vendors", inserted_vendors)
    return inserted_vendors


def ensure_vendor_seed_data(db: Session, excel_path: Path) -> bool:
    """Seed vendor workbook data once if vendor master table is empty."""
    existing_count = db.query(Vendor).count()
    if existing_count > 0:
        return False

    seed_vendor_tables_from_excel(db=db, excel_path=excel_path)
    return True
