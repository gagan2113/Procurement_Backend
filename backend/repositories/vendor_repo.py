from typing import Dict, List, Optional, Sequence

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.models.vendor import Contract, MaterialVendorMap, PurchaseHistory, Vendor, VendorPerformance


def list_vendors(
	db: Session,
	search: Optional[str] = None,
	category: Optional[str] = None,
	skip: int = 0,
	limit: int = 50,
) -> tuple[List[Vendor], int]:
	query = db.query(Vendor)

	if search:
		term = f"%{search.strip().lower()}%"
		query = query.filter(
			or_(
				func.lower(Vendor.vendor_id).like(term),
				func.lower(Vendor.vendor_name).like(term),
				func.lower(Vendor.city).like(term),
				func.lower(Vendor.email).like(term),
			)
		)

	if category:
		query = query.filter(func.lower(Vendor.category) == category.strip().lower())

	total = query.count()
	items = query.order_by(Vendor.vendor_name.asc()).offset(skip).limit(limit).all()
	return items, total


def get_vendor_by_id(db: Session, vendor_id: str) -> Optional[Vendor]:
	return db.query(Vendor).filter(Vendor.vendor_id == vendor_id).first()


def get_purchase_history_by_vendor_id(db: Session, vendor_id: str) -> List[PurchaseHistory]:
	return (
		db.query(PurchaseHistory)
		.filter(PurchaseHistory.vendor_id == vendor_id)
		.order_by(PurchaseHistory.po_date.desc(), PurchaseHistory.deal_id.desc())
		.all()
	)


def get_vendor_performance_by_vendor_id(db: Session, vendor_id: str) -> Optional[VendorPerformance]:
	return db.query(VendorPerformance).filter(VendorPerformance.vendor_id == vendor_id).first()


def get_contracts_by_vendor_id(db: Session, vendor_id: str) -> List[Contract]:
	return (
		db.query(Contract)
		.filter(Contract.vendor_id == vendor_id)
		.order_by(Contract.end_date.desc(), Contract.contract_id.desc())
		.all()
	)


def get_material_map_by_vendor_id(db: Session, vendor_id: str) -> List[MaterialVendorMap]:
	return (
		db.query(MaterialVendorMap)
		.filter(
			or_(
				MaterialVendorMap.primary_vendor_id == vendor_id,
				MaterialVendorMap.secondary_vendor_id == vendor_id,
				MaterialVendorMap.preferred_vendor_id == vendor_id,
			)
		)
		.order_by(MaterialVendorMap.material_code.asc())
		.all()
	)


def get_order_count_by_vendor_ids(db: Session, vendor_ids: Sequence[str]) -> Dict[str, int]:
	if not vendor_ids:
		return {}

	rows = (
		db.query(PurchaseHistory.vendor_id, func.count(PurchaseHistory.deal_id))
		.filter(PurchaseHistory.vendor_id.in_(vendor_ids))
		.group_by(PurchaseHistory.vendor_id)
		.all()
	)
	return {vendor_id: int(count) for vendor_id, count in rows}


def get_performance_by_vendor_ids(db: Session, vendor_ids: Sequence[str]) -> Dict[str, VendorPerformance]:
	if not vendor_ids:
		return {}

	rows = db.query(VendorPerformance).filter(VendorPerformance.vendor_id.in_(vendor_ids)).all()
	return {row.vendor_id: row for row in rows}


def get_material_count_by_vendor_ids(db: Session, vendor_ids: Sequence[str]) -> Dict[str, int]:
	if not vendor_ids:
		return {}

	counts: Dict[str, set] = {vendor_id: set() for vendor_id in vendor_ids}
	rows = (
		db.query(MaterialVendorMap)
		.filter(
			or_(
				MaterialVendorMap.primary_vendor_id.in_(vendor_ids),
				MaterialVendorMap.secondary_vendor_id.in_(vendor_ids),
				MaterialVendorMap.preferred_vendor_id.in_(vendor_ids),
			)
		)
		.all()
	)

	for row in rows:
		for candidate in (row.primary_vendor_id, row.secondary_vendor_id, row.preferred_vendor_id):
			if candidate in counts and row.material_code:
				counts[candidate].add(row.material_code)

	return {vendor_id: len(material_codes) for vendor_id, material_codes in counts.items()}


def get_preferred_vendor_ids(db: Session, vendor_ids: Sequence[str]) -> set[str]:
	if not vendor_ids:
		return set()

	rows = (
		db.query(MaterialVendorMap.preferred_vendor_id)
		.filter(MaterialVendorMap.preferred_vendor_id.in_(vendor_ids))
		.distinct()
		.all()
	)
	return {row[0] for row in rows if row[0]}
