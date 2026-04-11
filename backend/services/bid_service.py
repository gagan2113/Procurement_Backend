from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.config.constants import RFQStatus
from backend.repositories import bid_repo, rfq_repo, vendor_repo
from backend.schemas.bid_schema import BidSubmitRequest
from backend.utils.response_formatter import success_response


def _normalize_low_is_better(value: float, min_value: float, max_value: float) -> float:
	if max_value == min_value:
		return 1.0
	score = (max_value - value) / (max_value - min_value)
	return max(0.0, min(1.0, score))


def _quality_normalized(technical_pct: float, quality_score: float) -> float:
	technical_component = max(0.0, min(technical_pct, 100.0)) / 100.0
	quality_component = max(0.0, min(quality_score, 10.0)) / 10.0
	return max(0.0, min(1.0, (technical_component * 0.65) + (quality_component * 0.35)))


def _risk_component(performance) -> float:
	if not performance:
		return 0.5

	defect = float(performance.defect_rate_pct or 0.0)
	delay = max(float(performance.avg_delay_days or 0.0), 0.0)
	on_time = float(performance.on_time_delivery_pct or 0.0)

	defect_penalty = min(1.0, defect / 5.0)
	delay_penalty = min(1.0, delay / 10.0)
	on_time_penalty = max(0.0, (95.0 - on_time) / 95.0)

	penalty = (defect_penalty * 0.45) + (delay_penalty * 0.35) + (on_time_penalty * 0.20)
	return max(0.0, min(1.0, 1.0 - penalty))


def _build_ai_insight(
	*,
	vendor_name: str,
	price_norm: float,
	delivery_norm: float,
	quality_norm: float,
	risk_norm: float,
	final_score: float,
) -> tuple[list[str], list[str], str]:
	strengths: list[str] = []
	risks: list[str] = []

	if price_norm >= 0.75:
		strengths.append("Competitive pricing")
	if delivery_norm >= 0.75:
		strengths.append("Faster delivery commitment")
	if quality_norm >= 0.75:
		strengths.append("Strong technical and quality response")
	if risk_norm >= 0.70:
		strengths.append("Low historical execution risk")

	if price_norm <= 0.35:
		risks.append("Higher quoted price than peers")
	if delivery_norm <= 0.35:
		risks.append("Longer delivery timeline")
	if quality_norm <= 0.55:
		risks.append("Technical and quality commitments are weaker")
	if risk_norm <= 0.45:
		risks.append("Historical delay or defect risk")

	if not strengths:
		strengths.append("Balanced bid profile")
	if not risks:
		risks.append("No major risk signals detected")

	if final_score >= 80 and risk_norm >= 0.60:
		recommendation = "Preferred"
	elif final_score >= 60:
		recommendation = "Consider"
	else:
		recommendation = "Avoid"

	return strengths, risks, recommendation


def _serialize_bid(bid) -> dict:
	return {
		"bid_id": bid.id,
		"rfq_id": bid.rfq_id,
		"vendor_id": bid.vendor_id,
		"vendor_name": bid.vendor_name,
		"quoted_price": round(float(bid.quoted_price), 2),
		"currency": bid.currency,
		"quoted_delivery_days": int(bid.quoted_delivery_days),
		"technical_compliance_pct": round(float(bid.technical_compliance_pct), 2),
		"quality_commitment_score": round(float(bid.quality_commitment_score), 2),
		"warranty_months": int(bid.warranty_months or 0),
		"payment_terms_days": bid.payment_terms_days,
		"normalized_price": round(float(bid.normalized_price), 4) if bid.normalized_price is not None else None,
		"normalized_delivery": round(float(bid.normalized_delivery), 4) if bid.normalized_delivery is not None else None,
		"normalized_quality": round(float(bid.normalized_quality), 4) if bid.normalized_quality is not None else None,
		"status": bid.status,
		"updated_at": bid.updated_at.isoformat() if bid.updated_at else None,
	}


def _serialize_evaluation(row) -> dict:
	return {
		"bid_id": row.bid_id,
		"vendor_id": row.vendor_id,
		"vendor_name": row.vendor_name,
		"price_score": round(float(row.price_score), 2),
		"delivery_score": round(float(row.delivery_score), 2),
		"quality_score": round(float(row.quality_score), 2),
		"risk_score": round(float(row.risk_score), 2),
		"final_score": round(float(row.final_score), 2),
		"rank": int(row.rank),
		"recommendation": row.recommendation,
		"is_selected": bool(row.is_selected),
	}


def _build_bundle_from_db(db: Session, rfq_id: str) -> dict:
	bids = bid_repo.list_bids_by_rfq(db=db, rfq_id=rfq_id)
	evaluations = bid_repo.list_evaluations_by_rfq(db=db, rfq_id=rfq_id)

	ai_insights = {
		row.vendor_id: {
			"vendor_name": row.vendor_name,
			"strengths": list(row.strengths or []),
			"risks": list(row.risks or []),
			"recommendation": row.recommendation,
		}
		for row in evaluations
	}

	return {
		"bids": [_serialize_bid(bid) for bid in bids],
		"evaluation": [_serialize_evaluation(item) for item in evaluations],
		"ai_insights": ai_insights,
	}


def _get_rfq_or_404(db: Session, rfq_id: str):
	rfq = rfq_repo.get_rfq_by_id(db=db, rfq_id=rfq_id)
	if not rfq:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"RFQ '{rfq_id}' not found.",
		)
	return rfq


def _evaluate_open_rfq_bundle(db: Session, rfq) -> dict:
	if rfq.status != RFQStatus.OPEN.value:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Only RFQs in 'open' status can be evaluated.",
		)

	bids = bid_repo.list_bids_by_rfq(db=db, rfq_id=rfq.id)
	if not bids:
		return {
			"bids": [],
			"evaluation": [],
			"ai_insights": {},
		}

	prices = [float(bid.quoted_price) for bid in bids]
	delivery_days = [float(bid.quoted_delivery_days) for bid in bids]
	min_price, max_price = min(prices), max(prices)
	min_delivery, max_delivery = min(delivery_days), max(delivery_days)

	vendor_ids = [bid.vendor_id for bid in bids]
	performance_map = vendor_repo.get_performance_by_vendor_ids(db=db, vendor_ids=vendor_ids)

	interim_rows = []
	for bid in bids:
		price_norm = _normalize_low_is_better(float(bid.quoted_price), min_price, max_price)
		delivery_norm = _normalize_low_is_better(float(bid.quoted_delivery_days), min_delivery, max_delivery)
		quality_norm = _quality_normalized(
			technical_pct=float(bid.technical_compliance_pct),
			quality_score=float(bid.quality_commitment_score),
		)
		risk_norm = _risk_component(performance_map.get(bid.vendor_id))

		price_score = price_norm * 100.0
		delivery_score = delivery_norm * 100.0
		quality_score = quality_norm * 100.0
		risk_score = risk_norm * 100.0

		final_score = (
			(price_score * 0.40)
			+ (delivery_score * 0.25)
			+ (quality_score * 0.25)
			+ (risk_score * 0.10)
		)

		strengths, risks, recommendation = _build_ai_insight(
			vendor_name=bid.vendor_name,
			price_norm=price_norm,
			delivery_norm=delivery_norm,
			quality_norm=quality_norm,
			risk_norm=risk_norm,
			final_score=final_score,
		)

		bid_repo.update_bid_normalization(
			db=db,
			bid=bid,
			normalized_price=price_norm,
			normalized_delivery=delivery_norm,
			normalized_quality=quality_norm,
			normalization_meta={
				"min_price": round(min_price, 4),
				"max_price": round(max_price, 4),
				"min_delivery_days": round(min_delivery, 4),
				"max_delivery_days": round(max_delivery, 4),
				"normalized_at": datetime.utcnow().isoformat(),
			},
		)

		interim_rows.append(
			{
				"bid_id": bid.id,
				"vendor_id": bid.vendor_id,
				"vendor_name": bid.vendor_name,
				"price_score": round(price_score, 2),
				"delivery_score": round(delivery_score, 2),
				"quality_score": round(quality_score, 2),
				"risk_score": round(risk_score, 2),
				"final_score": round(final_score, 2),
				"strengths": strengths,
				"risks": risks,
				"recommendation": recommendation,
			}
		)

	ranked_rows = sorted(
		interim_rows,
		key=lambda row: (row["final_score"], row["quality_score"], row["delivery_score"]),
		reverse=True,
	)

	for idx, row in enumerate(ranked_rows, start=1):
		row["rank"] = idx
		row["is_selected"] = False

	bid_repo.replace_evaluations(db=db, rfq_id=rfq.id, rows=ranked_rows)
	return _build_bundle_from_db(db=db, rfq_id=rfq.id)


async def submit_bid(db: Session, rfq_id: str, payload: BidSubmitRequest) -> dict:
	rfq = _get_rfq_or_404(db=db, rfq_id=rfq_id)
	if rfq.status != RFQStatus.OPEN.value:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Bids can only be submitted for RFQs in 'open' status.",
		)

	vendor = vendor_repo.get_vendor_by_id(db=db, vendor_id=payload.vendor_id)
	if not vendor:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"Vendor '{payload.vendor_id}' not found.",
		)

	bid_repo.create_or_update_bid(
		db=db,
		rfq_id=rfq.id,
		vendor_id=vendor.vendor_id,
		vendor_name=vendor.vendor_name,
		quoted_price=payload.quoted_price,
		currency=payload.currency,
		quoted_delivery_days=payload.quoted_delivery_days,
		technical_compliance_pct=payload.technical_compliance_pct,
		quality_commitment_score=payload.quality_commitment_score,
		warranty_months=payload.warranty_months,
		payment_terms_days=payload.payment_terms_days,
		notes=payload.notes,
	)

	# Re-evaluate immediately so frontend dashboards can reflect latest standings in real time.
	bundle = _evaluate_open_rfq_bundle(db=db, rfq=rfq)
	return success_response(data=bundle, message="Bid submitted and evaluation updated successfully.")


async def evaluate_bids(db: Session, rfq_id: str) -> dict:
	rfq = _get_rfq_or_404(db=db, rfq_id=rfq_id)
	bundle = _evaluate_open_rfq_bundle(db=db, rfq=rfq)
	return success_response(data=bundle, message="Bids evaluated successfully.")


async def get_live_evaluation(db: Session, rfq_id: str) -> dict:
	rfq = _get_rfq_or_404(db=db, rfq_id=rfq_id)
	if rfq.status == RFQStatus.OPEN.value:
		bundle = _evaluate_open_rfq_bundle(db=db, rfq=rfq)
	else:
		bundle = _build_bundle_from_db(db=db, rfq_id=rfq.id)
	return success_response(data=bundle, message="Live bid evaluation fetched successfully.")


async def select_vendor_and_close_rfq(db: Session, rfq_id: str, vendor_id: str) -> dict:
	rfq = _get_rfq_or_404(db=db, rfq_id=rfq_id)
	if rfq.status != RFQStatus.OPEN.value:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Vendor selection is only allowed for RFQs in 'open' status.",
		)

	# Ensure latest normalized scoring before final selection.
	_evaluate_open_rfq_bundle(db=db, rfq=rfq)
	selected = bid_repo.select_vendor_in_evaluations(db=db, rfq_id=rfq.id, vendor_id=vendor_id)
	if not selected:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"No evaluated bid found for vendor '{vendor_id}' in RFQ '{rfq_id}'.",
		)

	rfq_repo.close_rfq(db=db, rfq=rfq)
	bundle = _build_bundle_from_db(db=db, rfq_id=rfq.id)
	bundle["rfq_status"] = RFQStatus.CLOSED.value
	bundle["selected_vendor_id"] = selected.vendor_id
	bundle["selected_vendor_name"] = selected.vendor_name

	return success_response(data=bundle, message="Vendor selected and RFQ closed successfully.")
