from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Dict, Iterable, List, Optional, Sequence

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from backend.config.constants import DistributionStatus, RFQStatus
from backend.models.rfq import RFQ, RFQDistribution
from backend.models.vendor import Contract, MaterialVendorMap, PurchaseHistory, Vendor, VendorPerformance


def _generate_rfq_number(db: Session) -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    prefix = f"RFQ-{today}-"
    count = db.query(RFQ).filter(RFQ.rfq_number.like(f"{prefix}%")).count()
    return f"{prefix}{(count + 1):04d}"


def create_rfq(
    db: Session,
    *,
    pr_id: str,
    pr_number: str,
    material_name: str,
    category: Optional[str],
    quantity: int,
    delivery_date: date,
    specifications: Optional[str],
    scope_of_work: Optional[str],
    technical_specifications: Optional[str],
    submission_deadline: Optional[datetime],
    payment_terms: Optional[str],
    evaluation_criteria: Optional[str],
) -> RFQ:
    rfq = RFQ(
        id=str(uuid.uuid4()),
        rfq_number=_generate_rfq_number(db),
        pr_id=pr_id,
        pr_number=pr_number,
        material_name=material_name,
        category=category,
        quantity=quantity,
        delivery_date=delivery_date,
        specifications=specifications,
        scope_of_work=scope_of_work,
        technical_specifications=technical_specifications,
        submission_deadline=submission_deadline,
        payment_terms=payment_terms,
        evaluation_criteria=evaluation_criteria,
        status=RFQStatus.DRAFT.value,
        invited_vendors_count=0,
    )
    db.add(rfq)
    db.commit()
    db.refresh(rfq)
    return rfq


def get_rfq_by_id(db: Session, rfq_id: str) -> Optional[RFQ]:
    return db.query(RFQ).filter(RFQ.id == rfq_id).first()


def get_rfq_by_pr_id(db: Session, pr_id: str) -> Optional[RFQ]:
    return db.query(RFQ).filter(RFQ.pr_id == pr_id).first()


def list_rfqs(db: Session, *, status_filter: Optional[str] = None, search: Optional[str] = None) -> List[RFQ]:
    query = db.query(RFQ)

    if status_filter:
        query = query.filter(func.lower(RFQ.status) == status_filter.lower())

    if search:
        like_term = f"%{search.lower()}%"
        query = query.filter(
            or_(
                func.lower(RFQ.rfq_number).like(like_term),
                func.lower(RFQ.pr_number).like(like_term),
                func.lower(RFQ.material_name).like(like_term),
                func.lower(func.coalesce(RFQ.category, "")).like(like_term),
            )
        )

    return query.order_by(RFQ.created_at.desc()).all()


def get_distribution_summary_by_rfq_ids(db: Session, rfq_ids: Sequence[str]) -> Dict[str, dict]:
    if not rfq_ids:
        return {}

    rows = (
        db.query(
            RFQDistribution.rfq_id,
            func.count(RFQDistribution.id),
            func.max(RFQDistribution.sent_at),
        )
        .filter(RFQDistribution.rfq_id.in_(rfq_ids))
        .group_by(RFQDistribution.rfq_id)
        .all()
    )

    return {
        rfq_id: {
            "vendors_invited_count": int(count or 0),
            "last_sent_at": max_sent_at,
        }
        for rfq_id, count, max_sent_at in rows
    }


def update_rfq_pdf_path(db: Session, rfq: RFQ, pdf_path: str) -> RFQ:
    rfq.pdf_path = pdf_path
    rfq.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(rfq)
    return rfq


def update_rfq_fields(db: Session, rfq: RFQ, updates: dict) -> RFQ:
    for field, value in updates.items():
        if hasattr(rfq, field):
            setattr(rfq, field, value)

    rfq.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(rfq)
    return rfq


def mark_rfq_as_published(db: Session, rfq: RFQ) -> RFQ:
    now = datetime.utcnow()
    rfq.status = RFQStatus.PUBLISHED.value
    if not rfq.published_at:
        rfq.published_at = now
    rfq.updated_at = now

    db.commit()
    db.refresh(rfq)
    return rfq


def mark_rfq_open_for_bidding(db: Session, rfq: RFQ, public_link: str) -> RFQ:
    now = datetime.utcnow()
    if not rfq.published_at:
        rfq.published_at = now

    rfq.status = RFQStatus.OPEN.value
    rfq.public_link = public_link
    if not rfq.open_for_bidding_at:
        rfq.open_for_bidding_at = now
    rfq.updated_at = now

    db.commit()
    db.refresh(rfq)
    return rfq


def update_rfq_distribution_metrics(
    db: Session,
    *,
    rfq: RFQ,
    invited_vendors_count: int,
    last_sent_at: datetime,
) -> RFQ:
    rfq.invited_vendors_count = invited_vendors_count
    rfq.last_sent_at = last_sent_at
    rfq.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(rfq)
    return rfq


def close_rfq(db: Session, rfq: RFQ) -> RFQ:
    rfq.status = RFQStatus.CLOSED.value
    rfq.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(rfq)
    return rfq


def delete_rfq_with_relations(db: Session, rfq: RFQ) -> None:
    # Keep cleanup explicit to avoid orphaned RFQ-linked records.
    from backend.models.bid import Bid, BidEvaluation

    db.query(BidEvaluation).filter(BidEvaluation.rfq_id == rfq.id).delete()
    db.query(Bid).filter(Bid.rfq_id == rfq.id).delete()
    db.query(RFQDistribution).filter(RFQDistribution.rfq_id == rfq.id).delete()
    db.delete(rfq)
    db.commit()


def get_material_mapped_vendor_ids(db: Session, material_name: str, category: Optional[str]) -> set[str]:
    query = db.query(MaterialVendorMap).filter(
        or_(
            func.lower(MaterialVendorMap.material_description).like(f"%{material_name.lower()}%"),
            func.lower(MaterialVendorMap.material_code) == material_name.lower(),
        )
    )

    rows = query.all()
    if not rows and category:
        rows = db.query(MaterialVendorMap).filter(func.lower(MaterialVendorMap.category) == category.lower()).all()

    vendor_ids: set[str] = set()
    for row in rows:
        for candidate in (row.primary_vendor_id, row.secondary_vendor_id, row.preferred_vendor_id):
            if candidate:
                vendor_ids.add(candidate)
    return vendor_ids


def get_past_deal_vendor_ids(db: Session, material_name: str, category: Optional[str]) -> set[str]:
    query = db.query(PurchaseHistory).filter(
        func.lower(PurchaseHistory.material_or_service).like(f"%{material_name.lower()}%")
    )
    rows = query.all()
    if not rows and category:
        rows = db.query(PurchaseHistory).filter(func.lower(PurchaseHistory.category) == category.lower()).all()

    return {row.vendor_id for row in rows if row.vendor_id}


def get_vendors_by_ids(db: Session, vendor_ids: Sequence[str]) -> List[Vendor]:
    if not vendor_ids:
        return []
    return db.query(Vendor).filter(Vendor.vendor_id.in_(vendor_ids)).all()


def get_vendor_performance_map(db: Session, vendor_ids: Sequence[str]) -> Dict[str, VendorPerformance]:
    if not vendor_ids:
        return {}
    rows = db.query(VendorPerformance).filter(VendorPerformance.vendor_id.in_(vendor_ids)).all()
    return {row.vendor_id: row for row in rows}


def get_vendor_past_order_count(db: Session, vendor_ids: Sequence[str]) -> Dict[str, int]:
    if not vendor_ids:
        return {}
    rows = (
        db.query(PurchaseHistory.vendor_id, func.count(PurchaseHistory.deal_id))
        .filter(PurchaseHistory.vendor_id.in_(vendor_ids))
        .group_by(PurchaseHistory.vendor_id)
        .all()
    )
    return {vendor_id: int(count) for vendor_id, count in rows}


def get_active_contract_vendor_ids(db: Session, vendor_ids: Sequence[str]) -> set[str]:
    if not vendor_ids:
        return set()

    today = date.today()
    rows = (
        db.query(Contract.vendor_id)
        .filter(Contract.vendor_id.in_(vendor_ids))
        .filter(
            or_(
                and_(Contract.end_date.isnot(None), Contract.end_date >= today),
                func.lower(Contract.status) == "active",
            )
        )
        .distinct()
        .all()
    )
    return {row[0] for row in rows if row[0]}


def get_preferred_vendor_ids_for_material(db: Session, material_name: str, category: Optional[str]) -> set[str]:
    query = db.query(MaterialVendorMap.preferred_vendor_id).filter(
        or_(
            func.lower(MaterialVendorMap.material_description).like(f"%{material_name.lower()}%"),
            func.lower(MaterialVendorMap.material_code) == material_name.lower(),
        )
    )

    rows = query.all()
    if not rows and category:
        rows = (
            db.query(MaterialVendorMap.preferred_vendor_id)
            .filter(func.lower(MaterialVendorMap.category) == category.lower())
            .all()
        )

    return {row[0] for row in rows if row[0]}


def get_vendor_ids_by_category(db: Session, category: Optional[str]) -> set[str]:
    if not category:
        return set()

    rows = db.query(Vendor.vendor_id).filter(func.lower(Vendor.category) == category.lower()).all()
    return {row[0] for row in rows if row[0]}


def get_distribution_by_rfq_and_vendor(db: Session, rfq_id: str, vendor_id: str) -> Optional[RFQDistribution]:
    return (
        db.query(RFQDistribution)
        .filter(RFQDistribution.rfq_id == rfq_id, RFQDistribution.vendor_id == vendor_id)
        .first()
    )


def upsert_distribution_entries(
    db: Session,
    *,
    rfq_id: str,
    vendor_payload: Iterable[dict],
) -> List[RFQDistribution]:
    now = datetime.utcnow()
    entries: List[RFQDistribution] = []

    for vendor in vendor_payload:
        existing = get_distribution_by_rfq_and_vendor(db=db, rfq_id=rfq_id, vendor_id=vendor["vendor_id"])
        if existing:
            existing.vendor_name = vendor["vendor_name"]
            existing.email = vendor.get("email")
            existing.email_status = DistributionStatus.SENT.value
            existing.portal_notification_status = DistributionStatus.SENT.value
            existing.sent_at = now
            entries.append(existing)
            continue

        entry = RFQDistribution(
            id=str(uuid.uuid4()),
            rfq_id=rfq_id,
            vendor_id=vendor["vendor_id"],
            vendor_name=vendor["vendor_name"],
            email=vendor.get("email"),
            email_status=DistributionStatus.SENT.value,
            portal_notification_status=DistributionStatus.SENT.value,
            sent_at=now,
        )
        db.add(entry)
        entries.append(entry)

    db.commit()
    for entry in entries:
        db.refresh(entry)
    return entries


def get_distributions_by_rfq_id(db: Session, rfq_id: str) -> List[RFQDistribution]:
    return (
        db.query(RFQDistribution)
        .filter(RFQDistribution.rfq_id == rfq_id)
        .order_by(RFQDistribution.created_at.desc())
        .all()
    )
