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
	price: float,
	currency: str,
	lead_time_days: int,
	delivery_schedule: str,
	delivery_terms: str,
	payment_terms: str,
	validity_days: int,
	specification_compliance: float,
	alternative_product: Optional[str],
	quotation_pdf_path: str,
	technical_sheet_path: str,
	compliance_documents_path: str,
	certifications_path: str,
	document_status: str,
	extracted_price: Optional[float],
	extracted_delivery_terms: Optional[str],
	extracted_conditions: Optional[str],
	extracted_compliance_details: Optional[str],
	document_summary: Optional[str],
	document_compliance_score: Optional[float],
) -> Bid:
	bid = get_bid_by_rfq_vendor(db=db, rfq_id=rfq_id, vendor_id=vendor_id)
	if bid:
		bid.vendor_name = vendor_name
		bid.price = price
		bid.currency = currency
		bid.lead_time_days = lead_time_days
		bid.delivery_schedule = delivery_schedule
		bid.delivery_terms = delivery_terms
		bid.payment_terms = payment_terms
		bid.validity_days = validity_days
		bid.specification_compliance = specification_compliance
		bid.alternative_product = alternative_product
		bid.quotation_pdf_path = quotation_pdf_path
		bid.technical_sheet_path = technical_sheet_path
		bid.compliance_documents_path = compliance_documents_path
		bid.certifications_path = certifications_path
		bid.document_status = document_status
		bid.extracted_price = extracted_price
		bid.extracted_delivery_terms = extracted_delivery_terms
		bid.extracted_conditions = extracted_conditions
		bid.extracted_compliance_details = extracted_compliance_details
		bid.document_summary = document_summary
		bid.document_compliance_score = document_compliance_score
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
		price=price,
		currency=currency,
		lead_time_days=lead_time_days,
		delivery_schedule=delivery_schedule,
		delivery_terms=delivery_terms,
		payment_terms=payment_terms,
		validity_days=validity_days,
		specification_compliance=specification_compliance,
		alternative_product=alternative_product,
		quotation_pdf_path=quotation_pdf_path,
		technical_sheet_path=technical_sheet_path,
		compliance_documents_path=compliance_documents_path,
		certifications_path=certifications_path,
		document_status=document_status,
		extracted_price=extracted_price,
		extracted_delivery_terms=extracted_delivery_terms,
		extracted_conditions=extracted_conditions,
		extracted_compliance_details=extracted_compliance_details,
		document_summary=document_summary,
		document_compliance_score=document_compliance_score,
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
			reliability_score=row.get("reliability_score"),
			capability_score=row.get("capability_score"),
			document_compliance_score=row.get("document_compliance_score"),
			final_score=row["final_score"],
			rank=row["rank"],
			is_selected=row.get("is_selected", False),
			manual_override=row.get("manual_override", False),
			score_breakdown=row.get("score_breakdown"),
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


def apply_manual_override(
	db: Session,
	*,
	rfq_id: str,
	vendor_id: str,
	override_score: Optional[float],
	recommendation: Optional[str],
	breakdown: Optional[dict],
) -> Optional[BidEvaluation]:
	target = (
		db.query(BidEvaluation)
		.filter(BidEvaluation.rfq_id == rfq_id, BidEvaluation.vendor_id == vendor_id)
		.first()
	)
	if not target:
		return None

	now = datetime.utcnow()
	if breakdown:
		target.price_score = float(breakdown.get("price", target.price_score))
		target.quality_score = float(breakdown.get("quality", target.quality_score))
		target.delivery_score = float(breakdown.get("delivery", target.delivery_score))
		target.reliability_score = float(breakdown.get("reliability", target.reliability_score or 0.0))
		target.capability_score = float(breakdown.get("capability", target.capability_score or 0.0))
		target.risk_score = float(breakdown.get("risk", target.risk_score))
		target.score_breakdown = breakdown

	if override_score is not None:
		target.final_score = float(override_score)
	elif breakdown:
		target.final_score = (
			(float(target.price_score) * 0.30)
			+ (float(target.quality_score) * 0.25)
			+ (float(target.delivery_score) * 0.20)
			+ (float(target.reliability_score or 0.0) * 0.15)
			+ (float(target.capability_score or 0.0) * 0.10)
		)

	if recommendation:
		target.recommendation = recommendation

	strengths = list(target.strengths or [])
	if "Manual override applied" not in strengths:
		strengths.append("Manual override applied")
	target.strengths = strengths
	target.manual_override = True
	target.updated_at = now

	db.commit()
	db.refresh(target)
	return target


def rerank_evaluations(db: Session, rfq_id: str) -> List[BidEvaluation]:
	rows = (
		db.query(BidEvaluation)
		.filter(BidEvaluation.rfq_id == rfq_id)
		.order_by(BidEvaluation.final_score.desc(), BidEvaluation.quality_score.desc(), BidEvaluation.delivery_score.desc())
		.all()
	)

	now = datetime.utcnow()
	for idx, row in enumerate(rows, start=1):
		row.rank = idx
		row.updated_at = now

	db.commit()
	for row in rows:
		db.refresh(row)
	return rows
