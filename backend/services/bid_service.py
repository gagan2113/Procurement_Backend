from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.config.constants import RFQStatus
from backend.config.settings import get_settings
from backend.repositories import bid_repo, rfq_repo, vendor_repo
from backend.schemas.bid_schema import BidManualOverrideRequest, BidSubmitRequest, SendForApprovalRequest
from backend.utils.response_formatter import success_response

settings = get_settings()


def _clip_score(value: float) -> float:
	return max(0.0, min(100.0, float(value)))


def _normalize_low_is_better(value: float, min_value: float, max_value: float) -> float:
	if max_value == min_value:
		return 1.0
	score = (max_value - value) / (max_value - min_value)
	return max(0.0, min(1.0, score))


def _quality_normalized(specification_compliance: float, document_compliance_score: Optional[float]) -> float:
	spec_component = _clip_score(specification_compliance) / 100.0
	doc_component = _clip_score(document_compliance_score or specification_compliance) / 100.0
	return max(0.0, min(1.0, (spec_component * 0.70) + (doc_component * 0.30)))


def _delivery_profile_component(delivery_schedule: str, delivery_terms: str) -> float:
	score = 0.45
	if len((delivery_schedule or "").strip()) >= 20:
		score += 0.20

	terms = (delivery_terms or "").lower()
	for keyword in ["ddp", "install", "sla", "penalty", "milestone", "door"]:
		if keyword in terms:
			score += 0.08

	return max(0.0, min(1.0, score))


def _historical_reliability_component(performance) -> float:
	if not performance:
		return 0.5

	defect = float(performance.defect_rate_pct or 0.0)
	delay = max(float(performance.avg_delay_days or 0.0), 0.0)
	on_time = float(performance.on_time_delivery_pct or 0.0)

	on_time_component = max(0.0, min(1.0, on_time / 100.0))
	defect_component = max(0.0, min(1.0, 1.0 - (defect / 5.0)))
	delay_component = max(0.0, min(1.0, 1.0 - (delay / 10.0)))

	return max(0.0, min(1.0, (on_time_component * 0.50) + (defect_component * 0.30) + (delay_component * 0.20)))


def _risk_indicator_score(bid, performance) -> tuple[float, list[str]]:
	penalty = 0.0
	risk_indicators: list[str] = []

	if (bid.document_compliance_score or 0.0) < 60.0:
		penalty += 20.0
		risk_indicators.append("Low document compliance confidence")

	if bid.validity_days < 15:
		penalty += 10.0
		risk_indicators.append("Short quotation validity window")

	payment_terms = (bid.payment_terms or "").lower()
	if "advance" in payment_terms:
		penalty += 8.0
		risk_indicators.append("Advance payment condition needs review")

	if "subject to" in (bid.extracted_conditions or "").lower():
		penalty += 7.0
		risk_indicators.append("Conditional clauses detected in quotation")

	if performance:
		if float(performance.defect_rate_pct or 0.0) > 1.5:
			penalty += 15.0
			risk_indicators.append("Historical defect rate is elevated")
		if float(performance.on_time_delivery_pct or 0.0) < 85.0:
			penalty += 15.0
			risk_indicators.append("Historical on-time delivery is below target")

	risk_score = max(0.0, min(100.0, 100.0 - penalty))
	return risk_score, risk_indicators


def _capability_score(bid) -> float:
	doc_component = _clip_score(bid.document_compliance_score or bid.specification_compliance)
	cert_component = 100.0 if bid.certifications_path else 60.0
	alternative_component = 78.0 if bid.alternative_product else 88.0

	score = (doc_component * 0.60) + (cert_component * 0.25) + (alternative_component * 0.15)
	return _clip_score(score)


def _build_ai_insight(
	*,
	vendor_name: str,
	price_score: float,
	quality_score: float,
	delivery_score: float,
	reliability_score: float,
	capability_score: float,
	risk_score: float,
	document_compliance_score: float,
	final_score: float,
	risk_indicators: list[str],
) -> tuple[list[str], list[str], str]:
	strengths: list[str] = []
	risks: list[str] = []

	if price_score >= 75:
		strengths.append("Competitive pricing against peer bids")
	if quality_score >= 75:
		strengths.append("Strong specification and quality compliance")
	if delivery_score >= 70:
		strengths.append("Reliable lead time and delivery commitment")
	if reliability_score >= 70:
		strengths.append("Healthy historical reliability track record")
	if capability_score >= 70:
		strengths.append("Documented capability and certifications are sufficient")

	if document_compliance_score < 60:
		risks.append("Document package has low compliance confidence")
	if risk_score < 60:
		risks.append("Overall risk indicators require internal review")
	if delivery_score < 50:
		risks.append("Delivery commitments appear weaker than peers")
	if quality_score < 55:
		risks.append("Specification compliance may need clarification")

	for indicator in risk_indicators:
		if indicator not in risks:
			risks.append(indicator)

	if not strengths:
		strengths.append("Balanced quote with no major advantages")
	if not risks:
		risks.append("No critical risk indicators detected")

	if final_score >= 82 and reliability_score >= 65 and document_compliance_score >= 70:
		recommendation = "Preferred"
	elif final_score >= 65:
		recommendation = "Consider"
	else:
		recommendation = "Avoid"

	return strengths, risks, recommendation


def _safe_filename(filename: str) -> str:
	cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", filename or "document")
	return cleaned[:120] if len(cleaned) > 120 else cleaned


def _quotation_upload_dir(rfq_id: str, vendor_id: str) -> Path:
	base = Path(settings.pdf_dir) / "quotations" / rfq_id / vendor_id
	base.mkdir(parents=True, exist_ok=True)
	return base


async def _save_upload_file(file: UploadFile, target_dir: Path, label: str) -> str:
	if not file or not file.filename:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail=f"{label} is required.",
		)

	file_name = f"{label}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{_safe_filename(file.filename)}"
	target_path = target_dir / file_name
	content = await file.read()
	if not content:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail=f"Uploaded file '{file.filename}' is empty.",
		)

	target_path.write_bytes(content)
	return str(target_path)


def _extract_document_intelligence(payload: BidSubmitRequest, document_paths: dict) -> dict:
	conditions = (
		f"Delivery schedule: {payload.delivery_schedule}. "
		f"Delivery terms: {payload.delivery_terms}. "
		f"Payment terms: {payload.payment_terms}. "
		f"Validity: {payload.validity} days."
	)

	cert_bonus = 5.0 if document_paths.get("certifications") else 0.0
	document_compliance_score = _clip_score(payload.specification_compliance + cert_bonus)

	summary = (
		f"Quotation analysed with declared price {payload.price:.2f} {payload.currency}, "
		f"lead time {payload.lead_time} days, and specification compliance {payload.specification_compliance:.1f}%"
	)

	return {
		"extracted_price": payload.price,
		"extracted_delivery_terms": payload.delivery_terms,
		"extracted_conditions": conditions,
		"extracted_compliance_details": (
			f"Compliance declared at {payload.specification_compliance:.1f}% with technical and certification documents provided."
		),
		"document_summary": summary,
		"document_compliance_score": document_compliance_score,
	}


def _serialize_bid(bid) -> dict:
	return {
		"bid_id": bid.id,
		"rfq_id": bid.rfq_id,
		"vendor_id": bid.vendor_id,
		"vendor_name": bid.vendor_name,
		"price": round(float(bid.price), 2),
		"currency": bid.currency,
		"lead_time": int(bid.lead_time_days),
		"delivery_schedule": bid.delivery_schedule,
		"delivery_terms": bid.delivery_terms,
		"payment_terms": bid.payment_terms,
		"validity": int(bid.validity_days),
		"specification_compliance": round(float(bid.specification_compliance), 2),
		"alternative_product": bid.alternative_product,
		"document_status": bid.document_status,
		"document_summary": bid.document_summary,
		"document_compliance_score": round(float(bid.document_compliance_score), 2)
		if bid.document_compliance_score is not None
		else None,
		"quotation_pdf": bid.quotation_pdf_path,
		"technical_sheet": bid.technical_sheet_path,
		"compliance_documents": bid.compliance_documents_path,
		"certifications": bid.certifications_path,
		"normalized_price": round(float(bid.normalized_price), 4) if bid.normalized_price is not None else None,
		"normalized_delivery": round(float(bid.normalized_delivery), 4) if bid.normalized_delivery is not None else None,
		"normalized_quality": round(float(bid.normalized_quality), 4) if bid.normalized_quality is not None else None,
		"status": bid.status,
		"updated_at": bid.updated_at.isoformat() if bid.updated_at else None,
	}


def _evaluation_breakdown(row) -> dict:
	if isinstance(row.score_breakdown, dict):
		return {
			"price": round(float(row.score_breakdown.get("price", row.price_score)), 2),
			"quality": round(float(row.score_breakdown.get("quality", row.quality_score)), 2),
			"delivery": round(float(row.score_breakdown.get("delivery", row.delivery_score)), 2),
			"reliability": round(float(row.score_breakdown.get("reliability", row.reliability_score or 0.0)), 2),
			"capability": round(float(row.score_breakdown.get("capability", row.capability_score or 0.0)), 2),
			"risk": round(float(row.score_breakdown.get("risk", row.risk_score)), 2),
		}

	return {
		"price": round(float(row.price_score), 2),
		"quality": round(float(row.quality_score), 2),
		"delivery": round(float(row.delivery_score), 2),
		"reliability": round(float(row.reliability_score or 0.0), 2),
		"capability": round(float(row.capability_score or 0.0), 2),
		"risk": round(float(row.risk_score), 2),
	}


def _serialize_evaluation(row) -> dict:
	return {
		"vendor_id": row.vendor_id,
		"vendor_name": row.vendor_name,
		"score": round(float(row.final_score), 2),
		"rank": int(row.rank),
		"breakdown": _evaluation_breakdown(row),
		"recommendation": row.recommendation,
		"manual_override": bool(row.manual_override),
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
			"risk_indicators": list(row.risks or []),
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


def _ensure_open_rfq(rfq) -> None:
	if rfq.status != RFQStatus.OPEN.value:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Only RFQs in 'Open for Bidding' status are eligible for bid operations.",
		)

	if rfq.submission_deadline and datetime.utcnow() > rfq.submission_deadline:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Bid submission deadline has passed. New bids are not allowed after expiry.",
		)


def _evaluate_open_rfq_bundle(db: Session, rfq) -> dict:
	if rfq.status != RFQStatus.OPEN.value:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Only RFQs in 'Open for Bidding' status can be evaluated.",
		)

	bids = bid_repo.list_bids_by_rfq(db=db, rfq_id=rfq.id)
	if not bids:
		return {
			"bids": [],
			"evaluation": [],
			"ai_insights": {},
		}

	prices = [float(bid.price) for bid in bids]
	lead_times = [float(bid.lead_time_days) for bid in bids]
	min_price, max_price = min(prices), max(prices)
	min_lead_time, max_lead_time = min(lead_times), max(lead_times)

	vendor_ids = [bid.vendor_id for bid in bids]
	performance_map = vendor_repo.get_performance_by_vendor_ids(db=db, vendor_ids=vendor_ids)

	interim_rows = []
	for bid in bids:
		performance = performance_map.get(bid.vendor_id)

		price_norm = _normalize_low_is_better(float(bid.price), min_price, max_price)
		lead_norm = _normalize_low_is_better(float(bid.lead_time_days), min_lead_time, max_lead_time)
		delivery_profile = _delivery_profile_component(bid.delivery_schedule, bid.delivery_terms)
		delivery_norm = max(0.0, min(1.0, (lead_norm * 0.75) + (delivery_profile * 0.25)))
		quality_norm = _quality_normalized(
			specification_compliance=float(bid.specification_compliance),
			document_compliance_score=bid.document_compliance_score,
		)

		historical_reliability = _historical_reliability_component(performance)
		risk_score, risk_indicators = _risk_indicator_score(bid, performance)
		reliability_score = _clip_score((historical_reliability * 100.0 * 0.70) + (risk_score * 0.30))
		capability_score = _capability_score(bid)

		price_score = _clip_score(price_norm * 100.0)
		delivery_score = _clip_score(delivery_norm * 100.0)
		quality_score = _clip_score(quality_norm * 100.0)

		final_score = _clip_score(
			(price_score * 0.30)
			+ (quality_score * 0.25)
			+ (delivery_score * 0.20)
			+ (reliability_score * 0.15)
			+ (capability_score * 0.10)
		)

		strengths, risks, recommendation = _build_ai_insight(
			vendor_name=bid.vendor_name,
			price_score=price_score,
			quality_score=quality_score,
			delivery_score=delivery_score,
			reliability_score=reliability_score,
			capability_score=capability_score,
			risk_score=risk_score,
			document_compliance_score=float(bid.document_compliance_score or bid.specification_compliance),
			final_score=final_score,
			risk_indicators=risk_indicators,
		)

		score_breakdown = {
			"price": round(price_score, 2),
			"quality": round(quality_score, 2),
			"delivery": round(delivery_score, 2),
			"reliability": round(reliability_score, 2),
			"capability": round(capability_score, 2),
			"risk": round(risk_score, 2),
		}

		bid_repo.update_bid_normalization(
			db=db,
			bid=bid,
			normalized_price=price_norm,
			normalized_delivery=delivery_norm,
			normalized_quality=quality_norm,
			normalization_meta={
				"min_price": round(min_price, 4),
				"max_price": round(max_price, 4),
				"min_lead_time_days": round(min_lead_time, 4),
				"max_lead_time_days": round(max_lead_time, 4),
				"risk_score": round(risk_score, 2),
				"reliability_score": round(reliability_score, 2),
				"capability_score": round(capability_score, 2),
				"document_compliance_score": round(float(bid.document_compliance_score or 0.0), 2),
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
				"reliability_score": round(reliability_score, 2),
				"capability_score": round(capability_score, 2),
				"document_compliance_score": round(float(bid.document_compliance_score or 0.0), 2),
				"final_score": round(final_score, 2),
				"score_breakdown": score_breakdown,
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
		row["manual_override"] = False

	bid_repo.replace_evaluations(db=db, rfq_id=rfq.id, rows=ranked_rows)
	return _build_bundle_from_db(db=db, rfq_id=rfq.id)


async def submit_bid_with_documents(
	db: Session,
	*,
	rfq_id: str,
	vendor_id: str,
	price: float,
	currency: str,
	lead_time: int,
	delivery_schedule: str,
	delivery_terms: str,
	payment_terms: str,
	validity: int,
	specification_compliance: float,
	alternative_product: Optional[str],
	quotation_pdf: UploadFile,
	technical_sheet: UploadFile,
	compliance_documents: UploadFile,
	certifications: UploadFile,
) -> dict:
	try:
		payload = BidSubmitRequest(
			vendor_id=vendor_id,
			price=price,
			currency=currency,
			lead_time=lead_time,
			delivery_schedule=delivery_schedule,
			delivery_terms=delivery_terms,
			payment_terms=payment_terms,
			validity=validity,
			specification_compliance=specification_compliance,
			alternative_product=alternative_product,
		)
	except ValidationError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.errors()) from exc

	rfq = _get_rfq_or_404(db=db, rfq_id=rfq_id)
	_ensure_open_rfq(rfq)

	vendor = vendor_repo.get_vendor_by_id(db=db, vendor_id=payload.vendor_id)
	if not vendor:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"Vendor '{payload.vendor_id}' not found.",
		)

	upload_dir = _quotation_upload_dir(rfq_id=rfq.id, vendor_id=payload.vendor_id)
	document_paths = {
		"quotation_pdf_path": await _save_upload_file(quotation_pdf, upload_dir, "quotation-pdf"),
		"technical_sheet_path": await _save_upload_file(technical_sheet, upload_dir, "technical-sheet"),
		"compliance_documents_path": await _save_upload_file(compliance_documents, upload_dir, "compliance-docs"),
		"certifications_path": await _save_upload_file(certifications, upload_dir, "certifications"),
	}

	extracted = _extract_document_intelligence(payload=payload, document_paths=document_paths)
	bid = bid_repo.create_or_update_bid(
		db=db,
		rfq_id=rfq.id,
		vendor_id=vendor.vendor_id,
		vendor_name=vendor.vendor_name,
		price=payload.price,
		currency=payload.currency,
		lead_time_days=payload.lead_time,
		delivery_schedule=payload.delivery_schedule,
		delivery_terms=payload.delivery_terms,
		payment_terms=payload.payment_terms,
		validity_days=payload.validity,
		specification_compliance=payload.specification_compliance,
		alternative_product=payload.alternative_product,
		quotation_pdf_path=document_paths["quotation_pdf_path"],
		technical_sheet_path=document_paths["technical_sheet_path"],
		compliance_documents_path=document_paths["compliance_documents_path"],
		certifications_path=document_paths["certifications_path"],
		document_status="processed",
		extracted_price=extracted["extracted_price"],
		extracted_delivery_terms=extracted["extracted_delivery_terms"],
		extracted_conditions=extracted["extracted_conditions"],
		extracted_compliance_details=extracted["extracted_compliance_details"],
		document_summary=extracted["document_summary"],
		document_compliance_score=extracted["document_compliance_score"],
	)

	return success_response(
		data={
			"rfq_id": rfq.id,
			"bid_id": bid.id,
			"vendor_id": bid.vendor_id,
			"status": bid.status,
			"document_status": bid.document_status,
			"document_summary": bid.document_summary,
			"compliance_score": round(float(bid.document_compliance_score or 0.0), 2),
			"submitted_at": bid.updated_at.isoformat() if bid.updated_at else None,
		},
		message="Bid submitted with documents and processed successfully.",
	)


async def list_bids_for_management(db: Session, rfq_id: str) -> dict:
	rfq = _get_rfq_or_404(db=db, rfq_id=rfq_id)
	bids = bid_repo.list_bids_by_rfq(db=db, rfq_id=rfq.id)

	payload = [
		{
			"bid_id": bid.id,
			"vendor_id": bid.vendor_id,
			"vendor_name": bid.vendor_name,
			"price": round(float(bid.price), 2),
			"currency": bid.currency,
			"lead_time": int(bid.lead_time_days),
			"document_status": bid.document_status,
			"document_summary": bid.document_summary,
			"submitted_at": bid.updated_at.isoformat() if bid.updated_at else None,
			"document_access": {
				"quotation_pdf": bid.quotation_pdf_path,
				"technical_sheet": bid.technical_sheet_path,
				"compliance_documents": bid.compliance_documents_path,
				"certifications": bid.certifications_path,
			},
		}
		for bid in bids
	]

	return success_response(
		data={
			"rfq_id": rfq.id,
			"status": rfq.status,
			"bids": payload,
			"actions": {
				"evaluation_trigger": f"/api/v1/bid/rfq/{rfq.id}/evaluate",
				"manual_override": f"/api/v1/bid/rfq/{rfq.id}/manual-override",
			},
		},
		message="Bid management view fetched successfully.",
	)


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


async def manual_override_bid_evaluation(db: Session, rfq_id: str, payload: BidManualOverrideRequest) -> dict:
	rfq = _get_rfq_or_404(db=db, rfq_id=rfq_id)
	if rfq.status != RFQStatus.OPEN.value:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Manual override is only allowed for RFQs in 'Open for Bidding' status.",
		)

	if payload.score is None and not payload.breakdown:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Provide either override score or score breakdown for manual override.",
		)

	if not bid_repo.list_evaluations_by_rfq(db=db, rfq_id=rfq.id):
		_evaluate_open_rfq_bundle(db=db, rfq=rfq)

	overridden = bid_repo.apply_manual_override(
		db=db,
		rfq_id=rfq.id,
		vendor_id=payload.vendor_id,
		override_score=payload.score,
		recommendation=payload.recommendation,
		breakdown=payload.breakdown,
	)
	if not overridden:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"No evaluated bid found for vendor '{payload.vendor_id}' in RFQ '{rfq_id}'.",
		)

	bid_repo.rerank_evaluations(db=db, rfq_id=rfq.id)
	bundle = _build_bundle_from_db(db=db, rfq_id=rfq.id)
	return success_response(data=bundle, message="Manual override applied successfully.")


async def send_for_approval(db: Session, rfq_id: str, payload: SendForApprovalRequest) -> dict:
	rfq = _get_rfq_or_404(db=db, rfq_id=rfq_id)
	if rfq.status != RFQStatus.OPEN.value:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Approval forwarding is only allowed for RFQs in 'Open for Bidding' status.",
		)

	if not bid_repo.list_evaluations_by_rfq(db=db, rfq_id=rfq.id):
		_evaluate_open_rfq_bundle(db=db, rfq=rfq)

	evaluations = bid_repo.list_evaluations_by_rfq(db=db, rfq_id=rfq.id)
	if not evaluations:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail="No evaluated vendors available to send for approval.",
		)

	target = evaluations[0]
	if payload.vendor_id:
		matched = [row for row in evaluations if row.vendor_id == payload.vendor_id]
		if not matched:
			raise HTTPException(
				status_code=status.HTTP_404_NOT_FOUND,
				detail=f"Vendor '{payload.vendor_id}' is not present in evaluated shortlist.",
			)
		target = matched[0]

	bid = bid_repo.get_bid_by_rfq_vendor(db=db, rfq_id=rfq.id, vendor_id=target.vendor_id)

	return success_response(
		data={
			"rfq_id": rfq.id,
			"vendor_id": target.vendor_id,
			"vendor_name": target.vendor_name,
			"score": round(float(target.final_score), 2),
			"rank": int(target.rank),
			"breakdown": _evaluation_breakdown(target),
			"recommendation": target.recommendation,
			"notes": payload.notes,
			"document_access": {
				"quotation_pdf": bid.quotation_pdf_path if bid else None,
				"technical_sheet": bid.technical_sheet_path if bid else None,
				"compliance_documents": bid.compliance_documents_path if bid else None,
				"certifications": bid.certifications_path if bid else None,
			},
		},
		message="Vendor shortlist sent for approval.",
	)


async def select_vendor_and_close_rfq(db: Session, rfq_id: str, vendor_id: str) -> dict:
	rfq = _get_rfq_or_404(db=db, rfq_id=rfq_id)
	if rfq.status != RFQStatus.OPEN.value:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Vendor selection is only allowed for RFQs in 'Open for Bidding' status.",
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


