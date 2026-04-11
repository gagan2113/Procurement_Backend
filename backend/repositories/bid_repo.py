from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.config.constants import BidStatus
from backend.models.bid import Bid, BidEvaluation


def get_bid_by_rfq_vendor(db: Session, rfq_id: str, vendor_id: str) -> Optional[Bid]:
	return db.query(Bid).filter(Bid.rfq_id == rfq_id, Bid.vendor_id == vendor_id).first()


def create_or_update_bid(
	db: Session,
	*,
	rfq_id: str,
	vendor_id: str,
	vendor_name: str,
	quoted_price: float,
	currency: str,
	quoted_delivery_days: int,
	technical_compliance_pct: float,
	quality_commitment_score: float,
	warranty_months: int,
	payment_terms_days: Optional[int],
	notes: Optional[str],
) -> Bid:
	bid = get_bid_by_rfq_vendor(db=db, rfq_id=rfq_id, vendor_id=vendor_id)
	if bid:
		bid.vendor_name = vendor_name
		bid.quoted_price = quoted_price
		bid.currency = currency
		bid.quoted_delivery_days = quoted_delivery_days
		bid.technical_compliance_pct = technical_compliance_pct
		bid.quality_commitment_score = quality_commitment_score
		bid.warranty_months = warranty_months
		bid.payment_terms_days = payment_terms_days
		bid.notes = notes
		bid.status = BidStatus.SUBMITTED.value
		bid.updated_at = datetime.utcnow()
		db.commit()
		db.refresh(bid)
		return bid

	bid = Bid(
		id=str(uuid.uuid4()),
		rfq_id=rfq_id,
		vendor_id=vendor_id,
		vendor_name=vendor_name,
		quoted_price=quoted_price,
		currency=currency,
		quoted_delivery_days=quoted_delivery_days,
		technical_compliance_pct=technical_compliance_pct,
		quality_commitment_score=quality_commitment_score,
		warranty_months=warranty_months,
		payment_terms_days=payment_terms_days,
		notes=notes,
		status=BidStatus.SUBMITTED.value,
	)
	db.add(bid)
	db.commit()
	db.refresh(bid)
	return bid


def list_bids_by_rfq(db: Session, rfq_id: str) -> List[Bid]:
	return (
		db.query(Bid)
		.filter(Bid.rfq_id == rfq_id)
		.order_by(Bid.updated_at.desc(), Bid.created_at.desc())
		.all()
	)


def update_bid_normalization(
	db: Session,
	*,
	bid: Bid,
	normalized_price: float,
	normalized_delivery: float,
	normalized_quality: float,
	normalization_meta: dict,
) -> Bid:
	bid.normalized_price = normalized_price
	bid.normalized_delivery = normalized_delivery
	bid.normalized_quality = normalized_quality
	bid.normalization_meta = normalization_meta
	bid.status = BidStatus.EVALUATED.value
	bid.updated_at = datetime.utcnow()
	db.commit()
	db.refresh(bid)
	return bid


def replace_evaluations(db: Session, rfq_id: str, rows: List[dict]) -> List[BidEvaluation]:
	db.query(BidEvaluation).filter(BidEvaluation.rfq_id == rfq_id).delete()

	created: List[BidEvaluation] = []
	now = datetime.utcnow()
	for row in rows:
		item = BidEvaluation(
			id=str(uuid.uuid4()),
			rfq_id=rfq_id,
			bid_id=row["bid_id"],
			vendor_id=row["vendor_id"],
			vendor_name=row["vendor_name"],
			price_score=row["price_score"],
			delivery_score=row["delivery_score"],
			quality_score=row["quality_score"],
			risk_score=row["risk_score"],
			final_score=row["final_score"],
			rank=row["rank"],
			is_selected=row.get("is_selected", False),
			strengths=row.get("strengths", []),
			risks=row.get("risks", []),
			recommendation=row.get("recommendation", "Consider"),
			created_at=now,
			updated_at=now,
		)
		db.add(item)
		created.append(item)

	db.commit()
	for item in created:
		db.refresh(item)
	return created


def list_evaluations_by_rfq(db: Session, rfq_id: str) -> List[BidEvaluation]:
	return (
		db.query(BidEvaluation)
		.filter(BidEvaluation.rfq_id == rfq_id)
		.order_by(BidEvaluation.rank.asc(), BidEvaluation.final_score.desc())
		.all()
	)


def select_vendor_in_evaluations(db: Session, rfq_id: str, vendor_id: str) -> Optional[BidEvaluation]:
	rows = list_evaluations_by_rfq(db=db, rfq_id=rfq_id)
	selected: Optional[BidEvaluation] = None
	now = datetime.utcnow()

	for row in rows:
		row.is_selected = row.vendor_id == vendor_id
		row.updated_at = now
		if row.is_selected:
			selected = row

	if not selected:
		return None

	bid = get_bid_by_rfq_vendor(db=db, rfq_id=rfq_id, vendor_id=vendor_id)
	if bid:
		bid.status = BidStatus.SELECTED.value
		bid.updated_at = now

	db.commit()
	db.refresh(selected)
	return selected
