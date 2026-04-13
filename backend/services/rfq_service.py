from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.config.constants import PRStatus, RFQStatus
from backend.repositories import request_repo, rfq_repo, vendor_repo
from backend.services.pdf_service import generate_rfq_pdf
from backend.utils.logger import get_logger
from backend.utils.response_formatter import success_response

HIGH_PERFORMANCE_MIN_SCORE = 70.0
HIGH_PERFORMANCE_MIN_ONTIME = 90.0

logger = get_logger(__name__)


def _status_label(status_value: str) -> str:
	mapping = {
		RFQStatus.DRAFT.value: "Draft",
		RFQStatus.PUBLISHED.value: "Published",
		RFQStatus.OPEN.value: "Open for Bidding",
		RFQStatus.CLOSED.value: "Closed",
	}
	return mapping.get(status_value, status_value)


def _normalize_status_filter(status_value: Optional[str]) -> Optional[str]:
	if not status_value:
		return None

	normalized = status_value.strip().lower().replace("_", " ")
	mapping = {
		"draft": RFQStatus.DRAFT.value,
		"published": RFQStatus.PUBLISHED.value,
		"open": RFQStatus.OPEN.value,
		"open for bidding": RFQStatus.OPEN.value,
		"closed": RFQStatus.CLOSED.value,
	}
	return mapping.get(normalized, normalized.replace(" ", "_"))


def _rfq_actions(status_value: str) -> list[str]:
	if status_value == RFQStatus.DRAFT.value:
		return ["Review", "Edit", "Delete", "Send to Vendors"]
	if status_value == RFQStatus.PUBLISHED.value:
		return ["Review", "Edit", "Send to Vendors", "Open for Bidding"]
	if status_value == RFQStatus.OPEN.value:
		return ["Review", "Send to Vendors", "Delete"]
	return ["Review"]


def _compute_performance_score(performance) -> Optional[float]:
	if not performance:
		return None
	if performance.ai_score is not None:
		return round(float(performance.ai_score), 1)

	on_time = float(performance.on_time_delivery_pct or 0.0)
	quality = float(performance.quality_score or 0.0) * 10.0
	price = float(performance.price_competitiveness or 0.0) * 10.0
	defect = float(performance.defect_rate_pct or 0.0)
	response_hours = float(performance.response_time_hours or 0.0)
	compliance = float(performance.compliance_score or 0.0) * 10.0

	response_component = max(0.0, 100.0 - (response_hours * 5.0))
	score = (
		(on_time * 0.30)
		+ (quality * 0.25)
		+ (price * 0.20)
		+ ((100.0 - defect) * 0.10)
		+ (response_component * 0.05)
		+ (compliance * 0.10)
	)
	return round(max(0.0, min(100.0, score)), 1)


def _is_high_performance(performance_score: Optional[float], performance) -> bool:
	if performance_score is not None and performance_score >= HIGH_PERFORMANCE_MIN_SCORE:
		return True
	if not performance:
		return False
	return float(performance.on_time_delivery_pct or 0.0) >= HIGH_PERFORMANCE_MIN_ONTIME


def _is_active_vendor(vendor, active_contract_vendor_ids: set[str]) -> bool:
	return bool(vendor.contract_exists) or vendor.vendor_id in active_contract_vendor_ids


def _default_scope_of_work(pr) -> str:
	return (
		f"Supply and delivery of {pr.item_name} in quantity {pr.quantity}. "
		f"Vendor must ensure fit-for-purpose quality, category compliance ({pr.category}), and full documentation."
	)


def _default_technical_specifications(pr) -> str:
	return (
		"Technical specifications should include applicable standards, configuration details, "
		"compatibility requirements, and quality/compliance certificates as relevant to the item category."
	)


def _default_evaluation_criteria() -> str:
	return (
		"Evaluation criteria: commercial competitiveness, delivery commitment, quality history, "
		"compliance adherence, and past performance score."
	)


def _default_payment_terms() -> str:
	return "Net 30 days from invoice acceptance unless overridden by contract."


def _build_submission_deadline(delivery_date: date) -> datetime:
	candidate = delivery_date - timedelta(days=5)
	min_allowed = date.today() + timedelta(days=2)
	final_date = candidate if candidate >= min_allowed else min_allowed
	return datetime.combine(final_date, time(hour=17, minute=0))


def _build_pdf_download_url(rfq_id: str) -> str:
	return f"/api/v1/rfq/{rfq_id}/pdf"


def _build_public_link(rfq_id: str) -> str:
	return f"/rfq/public/{rfq_id}"


def _build_bid_submit_url(rfq_id: str) -> str:
	return f"/api/v1/bid/rfq/{rfq_id}/submit"


def _to_path_if_exists(path_value: Optional[str]) -> Optional[Path]:
	if not path_value:
		return None
	path = Path(path_value)
	return path if path.exists() else None


def _ensure_rfq_pdf(db: Session, rfq) -> str:
	existing = _to_path_if_exists(rfq.pdf_path)
	if existing:
		return str(existing)

	pdf_path = generate_rfq_pdf(
		rfq_number=rfq.rfq_number,
		pr_number=rfq.pr_number,
		material_name=rfq.material_name,
		category=rfq.category,
		quantity=rfq.quantity,
		delivery_date=rfq.delivery_date,
		status=rfq.status,
		submission_deadline=rfq.submission_deadline,
		payment_terms=rfq.payment_terms,
		specifications=rfq.specifications,
		scope_of_work=rfq.scope_of_work,
		technical_specifications=rfq.technical_specifications,
		evaluation_criteria=rfq.evaluation_criteria,
		created_at=rfq.created_at,
	)
	rfq_repo.update_rfq_pdf_path(db=db, rfq=rfq, pdf_path=pdf_path)
	return pdf_path


def _serialize_rfq_card(rfq, distribution_summary: dict) -> dict:
	vendors_invited_count = int(
		rfq.invited_vendors_count
		if rfq.invited_vendors_count is not None
		else distribution_summary.get("vendors_invited_count", 0)
	)
	last_sent_at = rfq.last_sent_at or distribution_summary.get("last_sent_at")
	pdf_exists = _to_path_if_exists(rfq.pdf_path)

	return {
		"rfq_id": rfq.id,
		"rfq_number": rfq.rfq_number,
		"status": rfq.status,
		"status_label": _status_label(rfq.status),
		"actions_available": _rfq_actions(rfq.status),
		"pr_id": rfq.pr_id,
		"pr_number": rfq.pr_number,
		"material": rfq.material_name,
		"category": rfq.category,
		"quantity": rfq.quantity,
		"delivery_date": rfq.delivery_date.isoformat() if rfq.delivery_date else None,
		"submission_deadline": rfq.submission_deadline.isoformat() if rfq.submission_deadline else None,
		"vendors_invited_count": vendors_invited_count,
		"last_sent_at": last_sent_at.isoformat() if last_sent_at else None,
		"public_link": rfq.public_link,
		"pdf_available": bool(pdf_exists),
		"pdf_download_url": _build_pdf_download_url(rfq.id),
		"created_at": rfq.created_at.isoformat() if rfq.created_at else None,
		"updated_at": rfq.updated_at.isoformat() if rfq.updated_at else None,
	}


def _serialize_rfq_detail(rfq) -> dict:
	pdf_exists = _to_path_if_exists(rfq.pdf_path)
	return {
		"rfq_id": rfq.id,
		"rfq_number": rfq.rfq_number,
		"status": rfq.status,
		"status_label": _status_label(rfq.status),
		"actions_available": _rfq_actions(rfq.status),
		"pr_id": rfq.pr_id,
		"pr_number": rfq.pr_number,
		"material": rfq.material_name,
		"category": rfq.category,
		"quantity": rfq.quantity,
		"delivery_date": rfq.delivery_date.isoformat() if rfq.delivery_date else None,
		"specifications": rfq.specifications,
		"scope_of_work": rfq.scope_of_work,
		"technical_specifications": rfq.technical_specifications,
		"submission_deadline": rfq.submission_deadline.isoformat() if rfq.submission_deadline else None,
		"payment_terms": rfq.payment_terms,
		"evaluation_criteria": rfq.evaluation_criteria,
		"public_link": rfq.public_link,
		"vendors_invited_count": int(rfq.invited_vendors_count or 0),
		"last_sent_at": rfq.last_sent_at.isoformat() if rfq.last_sent_at else None,
		"pdf_available": bool(pdf_exists),
		"pdf_download_url": _build_pdf_download_url(rfq.id),
		"published_at": rfq.published_at.isoformat() if rfq.published_at else None,
		"open_for_bidding_at": rfq.open_for_bidding_at.isoformat() if rfq.open_for_bidding_at else None,
		"created_at": rfq.created_at.isoformat() if rfq.created_at else None,
		"updated_at": rfq.updated_at.isoformat() if rfq.updated_at else None,
	}


def _validate_rfq_completeness(rfq) -> list[str]:
	missing: list[str] = []

	required_fields = {
		"material_name": "material_name",
		"quantity": "quantity",
		"delivery_date": "delivery_date",
		"scope_of_work": "scope_of_work",
		"technical_specifications": "technical_specifications",
		"submission_deadline": "submission_deadline",
		"payment_terms": "payment_terms",
		"evaluation_criteria": "evaluation_criteria",
	}

	for attr, label in required_fields.items():
		value = getattr(rfq, attr, None)
		if value is None:
			missing.append(label)
			continue
		if isinstance(value, str) and not value.strip():
			missing.append(label)

	if rfq.quantity is not None and int(rfq.quantity) <= 0 and "quantity" not in missing:
		missing.append("quantity")

	if rfq.submission_deadline and rfq.submission_deadline <= datetime.utcnow():
		missing.append("submission_deadline_must_be_future")

	return sorted(set(missing))


def _serialize_distributions(distributions) -> list[dict]:
	return [
		{
			"vendor_id": row.vendor_id,
			"vendor_name": row.vendor_name,
			"email": row.email,
			"email_status": row.email_status,
			"portal_notification_status": row.portal_notification_status,
			"sent_at": row.sent_at.isoformat() if row.sent_at else None,
		}
		for row in distributions
	]


def _count_sent_notifications(distributions) -> tuple[int, int]:
	emails_sent = sum(1 for row in distributions if row.email_status == "sent")
	in_app_sent = sum(1 for row in distributions if row.portal_notification_status == "sent")
	return emails_sent, in_app_sent


def _phase_1_payload(rfq, emails_sent: int, in_app_sent: int) -> dict:
	return {
		"rfq": {
			"rfq_id": rfq.id,
			"status": _status_label(rfq.status),
			"public_link": rfq.public_link,
			"vendors_invited": int(rfq.invited_vendors_count or 0),
		},
		"notifications": {
			"emails_sent": int(emails_sent),
			"in_app_sent": int(in_app_sent),
		},
	}


def _refresh_rfq_distribution_metrics(db: Session, rfq):
	rows = rfq_repo.get_distributions_by_rfq_id(db=db, rfq_id=rfq.id)
	invited_count = len({row.vendor_id for row in rows})
	last_sent_at = max((row.sent_at for row in rows if row.sent_at), default=None)
	if not last_sent_at:
		last_sent_at = datetime.utcnow()

	return rfq_repo.update_rfq_distribution_metrics(
		db=db,
		rfq=rfq,
		invited_vendors_count=invited_count,
		last_sent_at=last_sent_at,
	)


def _require_editable_rfq_status(rfq):
	if rfq.status in {RFQStatus.OPEN.value, RFQStatus.CLOSED.value}:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Only RFQs in Draft or Published status can be edited.",
		)


def _require_deletable_rfq_status(rfq):
	if rfq.status == RFQStatus.CLOSED.value:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Closed RFQs cannot be deleted.",
		)


async def recommend_vendors(db: Session, material_name: str, category: Optional[str]) -> list[dict]:
	mapped_vendor_ids = rfq_repo.get_material_mapped_vendor_ids(db=db, material_name=material_name, category=category)
	deal_vendor_ids = rfq_repo.get_past_deal_vendor_ids(db=db, material_name=material_name, category=category)
	supplied_vendor_ids = mapped_vendor_ids | deal_vendor_ids

	candidate_vendor_ids = set(supplied_vendor_ids)
	if not candidate_vendor_ids:
		candidate_vendor_ids = rfq_repo.get_vendor_ids_by_category(db=db, category=category)

	vendors = rfq_repo.get_vendors_by_ids(db=db, vendor_ids=list(candidate_vendor_ids))
	if not vendors:
		return []

	vendor_ids = [vendor.vendor_id for vendor in vendors]
	performance_map = rfq_repo.get_vendor_performance_map(db=db, vendor_ids=vendor_ids)
	past_order_count = rfq_repo.get_vendor_past_order_count(db=db, vendor_ids=vendor_ids)
	active_contract_vendor_ids = rfq_repo.get_active_contract_vendor_ids(db=db, vendor_ids=vendor_ids)
	preferred_vendor_ids = rfq_repo.get_preferred_vendor_ids_for_material(
		db=db,
		material_name=material_name,
		category=category,
	)

	strict_matches: list[dict] = []
	relaxed_matches: list[dict] = []

	for vendor in vendors:
		performance = performance_map.get(vendor.vendor_id)
		score = _compute_performance_score(performance)
		active_vendor = _is_active_vendor(vendor, active_contract_vendor_ids)
		high_performance = _is_high_performance(score, performance)
		supplied_material = vendor.vendor_id in supplied_vendor_ids if supplied_vendor_ids else True

		payload = {
			"vendor_id": vendor.vendor_id,
			"vendor_name": vendor.vendor_name,
			"email": vendor.email,
			"performance_score": score,
			"past_orders_count": int(past_order_count.get(vendor.vendor_id, 0)),
			"preferred_tag": vendor.vendor_id in preferred_vendor_ids,
			"high_performing": high_performance,
			"active_vendor": active_vendor,
		}

		if supplied_material and high_performance and active_vendor:
			strict_matches.append(payload)
		elif supplied_material and active_vendor:
			relaxed_matches.append(payload)

	selected = strict_matches if strict_matches else relaxed_matches

	selected.sort(
		key=lambda item: (
			item["preferred_tag"],
			item["performance_score"] if item["performance_score"] is not None else -1,
			item["past_orders_count"],
		),
		reverse=True,
	)
	return selected


async def create_manual_rfq(db: Session, payload) -> dict:
	if payload.submission_deadline and payload.submission_deadline <= datetime.utcnow():
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="submission_deadline must be in the future.",
		)

	manual_pr_id = payload.pr_id or str(uuid.uuid4())
	manual_pr_number = payload.pr_number or f"MANUAL-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

	rfq = rfq_repo.create_rfq(
		db=db,
		pr_id=manual_pr_id,
		pr_number=manual_pr_number,
		material_name=payload.material_name,
		category=payload.category,
		quantity=payload.quantity,
		delivery_date=payload.delivery_date,
		specifications=payload.specifications,
		scope_of_work=payload.scope_of_work,
		technical_specifications=payload.technical_specifications,
		submission_deadline=payload.submission_deadline,
		payment_terms=payload.payment_terms,
		evaluation_criteria=payload.evaluation_criteria,
	)

	try:
		_ensure_rfq_pdf(db=db, rfq=rfq)
	except Exception as exc:
		logger.error("RFQ PDF generation failed for %s (non-fatal): %s", rfq.rfq_number, exc)

	recommendations = await recommend_vendors(db=db, material_name=rfq.material_name, category=rfq.category)
	pdf_exists = _to_path_if_exists(rfq.pdf_path)

	return success_response(
		data={
			"rfq_id": rfq.id,
			"rfq_number": rfq.rfq_number,
			"status": rfq.status,
			"status_label": _status_label(rfq.status),
			"actions_available": _rfq_actions(rfq.status),
			"vendor_recommendations": recommendations,
			"pdf_available": bool(pdf_exists),
			"pdf_download_url": _build_pdf_download_url(rfq.id),
		},
		message="RFQ draft created manually.",
	)


async def update_rfq(db: Session, rfq_id: str, payload) -> dict:
	rfq = rfq_repo.get_rfq_by_id(db=db, rfq_id=rfq_id)
	if not rfq:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"RFQ '{rfq_id}' not found.",
		)

	_require_editable_rfq_status(rfq)

	updates = payload.model_dump(exclude_unset=True)
	if not updates:
		return success_response(data=_serialize_rfq_detail(rfq), message="No RFQ changes were provided.")

	if "submission_deadline" in updates and updates["submission_deadline"]:
		if updates["submission_deadline"] <= datetime.utcnow():
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail="submission_deadline must be in the future.",
			)

	rfq = rfq_repo.update_rfq_fields(db=db, rfq=rfq, updates=updates)

	try:
		pdf_path = generate_rfq_pdf(
			rfq_number=rfq.rfq_number,
			pr_number=rfq.pr_number,
			material_name=rfq.material_name,
			category=rfq.category,
			quantity=rfq.quantity,
			delivery_date=rfq.delivery_date,
			status=rfq.status,
			submission_deadline=rfq.submission_deadline,
			payment_terms=rfq.payment_terms,
			specifications=rfq.specifications,
			scope_of_work=rfq.scope_of_work,
			technical_specifications=rfq.technical_specifications,
			evaluation_criteria=rfq.evaluation_criteria,
			created_at=rfq.created_at,
		)
		rfq = rfq_repo.update_rfq_pdf_path(db=db, rfq=rfq, pdf_path=pdf_path)
	except Exception as exc:
		logger.error("RFQ PDF regeneration failed for %s (non-fatal): %s", rfq.rfq_number, exc)

	return success_response(
		data=_serialize_rfq_detail(rfq),
		message=f"RFQ '{rfq.rfq_number}' updated successfully.",
	)


async def delete_rfq(db: Session, rfq_id: str) -> dict:
	rfq = rfq_repo.get_rfq_by_id(db=db, rfq_id=rfq_id)
	if not rfq:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"RFQ '{rfq_id}' not found.",
		)

	_require_deletable_rfq_status(rfq)
	rfq_repo.delete_rfq_with_relations(db=db, rfq=rfq)

	return success_response(
		data={
			"rfq_id": rfq_id,
			"deleted": True,
		},
		message="RFQ deleted successfully.",
	)


async def auto_create_rfq_for_approved_pr(db: Session, pr) -> dict:
	if pr.status != PRStatus.APPROVED.value:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="RFQ can only be auto-created for approved PRs.",
		)

	existing = rfq_repo.get_rfq_by_pr_id(db=db, pr_id=pr.id)
	if existing:
		recommendations = await recommend_vendors(db=db, material_name=existing.material_name, category=existing.category)
		existing_pdf = _to_path_if_exists(existing.pdf_path)
		return {
			"rfq_id": existing.id,
			"rfq_number": existing.rfq_number,
			"status": existing.status,
			"actions_available": _rfq_actions(existing.status),
			"vendor_recommendations": recommendations,
			"pdf_available": bool(existing_pdf),
			"pdf_download_url": _build_pdf_download_url(existing.id),
			"already_exists": True,
		}

	rfq = rfq_repo.create_rfq(
		db=db,
		pr_id=pr.id,
		pr_number=pr.pr_number,
		material_name=pr.item_name,
		category=pr.category,
		quantity=pr.quantity,
		delivery_date=pr.expected_delivery_date,
		specifications=pr.description,
		scope_of_work=_default_scope_of_work(pr),
		technical_specifications=_default_technical_specifications(pr),
		submission_deadline=_build_submission_deadline(pr.expected_delivery_date),
		payment_terms=_default_payment_terms(),
		evaluation_criteria=_default_evaluation_criteria(),
	)

	try:
		_ensure_rfq_pdf(db=db, rfq=rfq)
	except Exception as exc:
		logger.error("RFQ PDF generation failed for %s (non-fatal): %s", rfq.rfq_number, exc)

	recommendations = await recommend_vendors(db=db, material_name=rfq.material_name, category=rfq.category)
	pdf_exists = _to_path_if_exists(rfq.pdf_path)
	return {
		"rfq_id": rfq.id,
		"rfq_number": rfq.rfq_number,
		"status": rfq.status,
		"actions_available": _rfq_actions(rfq.status),
		"vendor_recommendations": recommendations,
		"pdf_available": bool(pdf_exists),
		"pdf_download_url": _build_pdf_download_url(rfq.id),
		"already_exists": False,
	}


async def create_rfq_for_approved_pr(db: Session, pr_id: str) -> dict:
	pr = request_repo.get_pr_by_id(db, pr_id)
	if not pr:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"Purchase Request with ID '{pr_id}' not found.",
		)

	payload = await auto_create_rfq_for_approved_pr(db=db, pr=pr)
	return success_response(data=payload, message="RFQ draft created from approved PR.")


async def list_rfqs(db: Session, status_filter: Optional[str] = None, search: Optional[str] = None) -> dict:
	normalized_status = _normalize_status_filter(status_filter)
	rfqs = rfq_repo.list_rfqs(db=db, status_filter=normalized_status, search=search)
	rfq_ids = [rfq.id for rfq in rfqs]
	distribution_summary = rfq_repo.get_distribution_summary_by_rfq_ids(db=db, rfq_ids=rfq_ids)

	payload = [
		_serialize_rfq_card(rfq, distribution_summary.get(rfq.id, {}))
		for rfq in rfqs
	]

	return success_response(
		data={
			"count": len(payload),
			"rfqs": payload,
		},
		message="RFQ list fetched successfully.",
	)


async def get_rfq_pdf_file(db: Session, rfq_id: str) -> tuple[str, str]:
	rfq = rfq_repo.get_rfq_by_id(db=db, rfq_id=rfq_id)
	if not rfq:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"RFQ '{rfq_id}' not found.",
		)

	try:
		pdf_path = _ensure_rfq_pdf(db=db, rfq=rfq)
	except Exception as exc:
		logger.error("Failed to build RFQ PDF for %s: %s", rfq.rfq_number, exc)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail="Unable to generate RFQ PDF at the moment.",
		) from exc

	pdf_file = Path(pdf_path)
	if not pdf_file.exists():
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail="RFQ PDF file not found.",
		)

	return str(pdf_file), f"{rfq.rfq_number}.pdf"


async def get_rfq_detail(db: Session, rfq_id: str) -> dict:
	rfq = rfq_repo.get_rfq_by_id(db=db, rfq_id=rfq_id)
	if not rfq:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"RFQ '{rfq_id}' not found.",
		)

	return success_response(
		data=_serialize_rfq_detail(rfq),
		message=f"RFQ '{rfq.rfq_number}' fetched successfully.",
	)


async def get_recommended_vendors(db: Session, rfq_id: str) -> dict:
	rfq = rfq_repo.get_rfq_by_id(db=db, rfq_id=rfq_id)
	if not rfq:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"RFQ '{rfq_id}' not found.",
		)

	vendors = await recommend_vendors(db=db, material_name=rfq.material_name, category=rfq.category)
	preferred = [vendor for vendor in vendors if vendor["preferred_tag"]]
	high_performing = [vendor for vendor in vendors if vendor["high_performing"]]

	return success_response(
		data={
			"rfq_id": rfq.id,
			"status": rfq.status,
			"vendors": vendors,
			"preferred_vendors": preferred,
			"high_performing_vendors": high_performing,
		},
		message="Recommended vendors fetched successfully.",
	)


async def publish_rfq(db: Session, rfq_id: str) -> dict:
	return await open_rfq_for_bidding(db=db, rfq_id=rfq_id)


async def open_rfq_for_bidding(db: Session, rfq_id: str) -> dict:
	rfq = rfq_repo.get_rfq_by_id(db=db, rfq_id=rfq_id)
	if not rfq:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"RFQ '{rfq_id}' not found.",
		)

	if rfq.status == RFQStatus.CLOSED.value:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Closed RFQ cannot be opened for bidding.",
		)

	if rfq.status == RFQStatus.DRAFT.value:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Send RFQ to vendors first to move Draft to Published before opening for bidding.",
		)

	public_link = rfq.public_link or _build_public_link(rfq.id)

	if rfq.status == RFQStatus.OPEN.value and rfq.public_link:
		updated = rfq
	else:
		updated = rfq_repo.mark_rfq_open_for_bidding(db=db, rfq=rfq, public_link=public_link)

	all_distributions = rfq_repo.get_distributions_by_rfq_id(db=db, rfq_id=updated.id)
	emails_sent, in_app_sent = _count_sent_notifications(all_distributions)

	return success_response(
		data={
			**_phase_1_payload(updated, emails_sent=emails_sent, in_app_sent=in_app_sent),
			"lifecycle_transition": ["Draft", "Published", "Open for Bidding"],
		},
		message="RFQ opened for bidding successfully.",
	)


async def send_rfq_to_vendors(db: Session, rfq_id: str, vendor_ids: list[str]) -> dict:
	rfq = rfq_repo.get_rfq_by_id(db=db, rfq_id=rfq_id)
	if not rfq:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"RFQ '{rfq_id}' not found.",
		)

	if rfq.status == RFQStatus.CLOSED.value:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Closed RFQ cannot be sent to vendors.",
		)

	missing_fields = _validate_rfq_completeness(rfq)
	if missing_fields:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail={
				"message": "RFQ is incomplete. Complete required fields before sending to vendors.",
				"missing_fields": missing_fields,
			},
		)

	if rfq.status == RFQStatus.DRAFT.value:
		rfq = rfq_repo.mark_rfq_as_published(db=db, rfq=rfq)
	elif rfq.status not in {RFQStatus.PUBLISHED.value, RFQStatus.OPEN.value}:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail=f"RFQ in status '{rfq.status}' cannot be sent to vendors.",
		)

	recommended = await recommend_vendors(db=db, material_name=rfq.material_name, category=rfq.category)
	if not recommended:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="No relevant vendors found based on material mapping, deal history, and performance.",
		)

	recommended_map = {vendor["vendor_id"]: vendor for vendor in recommended}
	requested_vendor_ids = {vendor_id.strip() for vendor_id in vendor_ids if vendor_id and vendor_id.strip()}
	if requested_vendor_ids:
		selected = [recommended_map[vendor_id] for vendor_id in requested_vendor_ids if vendor_id in recommended_map]
	else:
		selected = recommended

	if not selected:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Selected vendors are not relevant for this RFQ.",
		)

	distributions = rfq_repo.upsert_distribution_entries(
		db=db,
		rfq_id=rfq.id,
		vendor_payload=selected,
	)

	rfq = _refresh_rfq_distribution_metrics(db=db, rfq=rfq)
	emails_sent, in_app_sent = _count_sent_notifications(distributions)

	return success_response(
		data={
			**_phase_1_payload(rfq, emails_sent=emails_sent, in_app_sent=in_app_sent),
			"delivery_channel": ["email", "in_app_notification"],
			"distributions": _serialize_distributions(distributions),
		},
		message="RFQ sent to relevant vendors successfully.",
	)


async def get_public_rfq(db: Session, rfq_id: str, vendor_id: Optional[str] = None) -> dict:
	rfq = rfq_repo.get_rfq_by_id(db=db, rfq_id=rfq_id)
	if not rfq:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"RFQ '{rfq_id}' not found.",
		)

	if rfq.status not in {RFQStatus.PUBLISHED.value, RFQStatus.OPEN.value}:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="RFQ is not yet available for public/vendor participation.",
		)

	public_link = rfq.public_link or _build_public_link(rfq.id)
	if rfq.status == RFQStatus.PUBLISHED.value:
		rfq = rfq_repo.mark_rfq_open_for_bidding(db=db, rfq=rfq, public_link=public_link)
	elif not rfq.public_link:
		rfq = rfq_repo.update_rfq_fields(db=db, rfq=rfq, updates={"public_link": public_link})

	vendor_found = None
	if vendor_id:
		vendor_found = vendor_repo.get_vendor_by_id(db=db, vendor_id=vendor_id)

	deadline_expired = bool(rfq.submission_deadline and datetime.utcnow() > rfq.submission_deadline)

	return success_response(
		data={
			"rfq": {
				"rfq_id": rfq.id,
				"rfq_number": rfq.rfq_number,
				"status": _status_label(rfq.status),
				"material": rfq.material_name,
				"category": rfq.category,
				"quantity": rfq.quantity,
				"delivery_date": rfq.delivery_date.isoformat() if rfq.delivery_date else None,
				"submission_deadline": rfq.submission_deadline.isoformat() if rfq.submission_deadline else None,
				"scope_of_work": rfq.scope_of_work,
				"technical_specifications": rfq.technical_specifications,
				"payment_terms": rfq.payment_terms,
				"evaluation_criteria": rfq.evaluation_criteria,
				"public_link": rfq.public_link,
			},
			"access": {
				"public_access": True,
				"is_registered_vendor": bool(vendor_found),
				"registration_url": f"/api/v1/rfq/public/{rfq.id}/register",
				"submit_bid_action": {
					"method": "POST",
					"endpoint": _build_bid_submit_url(rfq.id),
					"enabled": bool(vendor_found) and not deadline_expired,
				},
				"deadline_expired": deadline_expired,
			},
		},
		message="Public RFQ details fetched successfully.",
	)


async def register_public_vendor_for_rfq(db: Session, rfq_id: str, payload) -> dict:
	rfq = rfq_repo.get_rfq_by_id(db=db, rfq_id=rfq_id)
	if not rfq:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"RFQ '{rfq_id}' not found.",
		)

	if rfq.status not in {RFQStatus.PUBLISHED.value, RFQStatus.OPEN.value}:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="RFQ is not open for vendor participation.",
		)

	email = payload.email.strip().lower()
	if "@" not in email or "." not in email:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="A valid email is required for registration.",
		)

	vendor = vendor_repo.get_vendor_by_email(db=db, email=email)
	is_new_vendor = False
	if not vendor:
		vendor = vendor_repo.create_public_vendor(
			db=db,
			vendor_name=payload.vendor_name,
			email=email,
			category=payload.category,
			contact_person=payload.contact_person,
			phone=payload.phone,
			city=payload.city,
			state=payload.state,
			country=payload.country,
		)
		is_new_vendor = True

	public_link = rfq.public_link or _build_public_link(rfq.id)
	if rfq.status == RFQStatus.PUBLISHED.value:
		rfq = rfq_repo.mark_rfq_open_for_bidding(db=db, rfq=rfq, public_link=public_link)
	elif not rfq.public_link:
		rfq = rfq_repo.update_rfq_fields(db=db, rfq=rfq, updates={"public_link": public_link})

	rfq_repo.upsert_distribution_entries(
		db=db,
		rfq_id=rfq.id,
		vendor_payload=[
			{
				"vendor_id": vendor.vendor_id,
				"vendor_name": vendor.vendor_name,
				"email": vendor.email,
			}
		],
	)

	rfq = _refresh_rfq_distribution_metrics(db=db, rfq=rfq)
	deadline_expired = bool(rfq.submission_deadline and datetime.utcnow() > rfq.submission_deadline)

	return success_response(
		data={
			"rfq_id": rfq.id,
			"vendor_id": vendor.vendor_id,
			"vendor_name": vendor.vendor_name,
			"new_registration": is_new_vendor,
			"status": _status_label(rfq.status),
			"public_link": rfq.public_link,
			"submit_bid_action": {
				"method": "POST",
				"endpoint": _build_bid_submit_url(rfq.id),
				"enabled": not deadline_expired,
			},
		},
		message="Vendor registration completed for RFQ participation.",
	)


async def list_open_rfqs_for_vendor_portal(db: Session, vendor_id: Optional[str] = None) -> dict:
	rfqs = rfq_repo.list_rfqs(db=db, status_filter=RFQStatus.OPEN.value)
	now = datetime.utcnow()
	payload: list[dict] = []

	for rfq in rfqs:
		rows = rfq_repo.get_distributions_by_rfq_id(db=db, rfq_id=rfq.id)
		invited_vendor_ids = {row.vendor_id for row in rows}

		if vendor_id and invited_vendor_ids and vendor_id not in invited_vendor_ids:
			continue

		deadline_expired = bool(rfq.submission_deadline and now > rfq.submission_deadline)
		payload.append(
			{
				"rfq_id": rfq.id,
				"rfq_number": rfq.rfq_number,
				"status": _status_label(rfq.status),
				"material": rfq.material_name,
				"category": rfq.category,
				"quantity": rfq.quantity,
				"delivery_date": rfq.delivery_date.isoformat() if rfq.delivery_date else None,
				"submission_deadline": rfq.submission_deadline.isoformat() if rfq.submission_deadline else None,
				"public_link": rfq.public_link,
				"vendors_invited": int(rfq.invited_vendors_count or 0),
				"is_invited": vendor_id in invited_vendor_ids if vendor_id else None,
				"submit_bid_action": {
					"method": "POST",
					"endpoint": _build_bid_submit_url(rfq.id),
					"enabled": not deadline_expired,
				},
				"deadline_expired": deadline_expired,
			}
		)

	return success_response(
		data={
			"count": len(payload),
			"rfqs": payload,
		},
		message="Open RFQs fetched for vendor portal.",
	)


async def list_rfq_distributions(db: Session, rfq_id: str) -> dict:
	rfq = rfq_repo.get_rfq_by_id(db=db, rfq_id=rfq_id)
	if not rfq:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"RFQ '{rfq_id}' not found.",
		)

	rows = rfq_repo.get_distributions_by_rfq_id(db=db, rfq_id=rfq_id)
	return success_response(
		data={
			"rfq_id": rfq.id,
			"status": rfq.status,
			"distributions": [
				{
					"vendor_id": row.vendor_id,
					"vendor_name": row.vendor_name,
					"email": row.email,
					"email_status": row.email_status,
					"portal_notification_status": row.portal_notification_status,
					"sent_at": row.sent_at.isoformat() if row.sent_at else None,
				}
				for row in rows
			],
		},
		message="RFQ distribution history fetched successfully.",
	)
