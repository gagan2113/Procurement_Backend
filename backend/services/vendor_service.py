from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.repositories import vendor_repo
from backend.utils.response_formatter import success_response

EXPIRING_DAYS_THRESHOLD = 60


def _round(value: Optional[float], digits: int = 2) -> Optional[float]:
	if value is None:
		return None
	return round(float(value), digits)


def _build_location(city: Optional[str], state: Optional[str], country: Optional[str]) -> str:
	parts = [part for part in [city, state, country] if part]
	return ", ".join(parts)


def _average(values: list[float]) -> Optional[float]:
	if not values:
		return None
	return sum(values) / len(values)


def _delivery_time_days(deal) -> Optional[float]:
	if deal.po_date and deal.actual_delivery:
		return float((deal.actual_delivery - deal.po_date).days)
	if deal.po_date and deal.delivery_date:
		return float((deal.delivery_date - deal.po_date).days)
	return None


def _delay_days(deal) -> float:
	if deal.actual_delivery and deal.delivery_date:
		return float((deal.actual_delivery - deal.delivery_date).days)
	return 0.0


def _compute_ai_score(performance) -> Optional[float]:
	if not performance:
		return None

	if performance.ai_score is not None:
		return float(performance.ai_score)

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
	return min(100.0, max(0.0, score))


def _risk_indicator(defect_rate_pct: Optional[float], avg_delay_days: Optional[float]) -> dict[str, Any]:
	defect = float(defect_rate_pct or 0.0)
	delay = max(float(avg_delay_days or 0.0), 0.0)
	risk_score = min(100.0, (defect * 25.0) + (delay * 12.0))

	if risk_score >= 55:
		level = "High"
	elif risk_score >= 25:
		level = "Medium"
	else:
		level = "Low"

	return {
		"level": level,
		"score": _round(risk_score, 1),
	}


def _derive_contract_status(end_date: Optional[date], fallback_status: Optional[str]) -> str:
	if not end_date:
		return fallback_status or "Active"

	days_to_expiry = (end_date - date.today()).days
	if days_to_expiry < 0:
		return "Expired"
	if days_to_expiry <= EXPIRING_DAYS_THRESHOLD:
		return "Expiring"
	return "Active"


def _recommendation(
	preferred_vendor: bool,
	ai_score: Optional[float],
	on_time_delivery_pct: Optional[float],
	defect_rate_pct: Optional[float],
	risk_level: str,
	active_contracts: int,
) -> str:
	if risk_level == "High" or (defect_rate_pct or 0.0) >= 2.0 or (on_time_delivery_pct or 0.0) < 85.0:
		return "Risky"

	if preferred_vendor and active_contracts > 0 and (ai_score or 0.0) >= 75.0:
		return "Preferred"

	return "Consider"


def _material_deals(deals: list, material_description: Optional[str]) -> list:
	if not material_description:
		return deals

	material_key = material_description.lower().strip()
	matched = []
	for deal in deals:
		entry = (deal.material_or_service or "").lower().strip()
		if not entry:
			continue
		if material_key in entry or entry in material_key:
			matched.append(deal)
	return matched or deals


async def list_vendor_cards(
	db: Session,
	search: Optional[str] = None,
	category: Optional[str] = None,
	skip: int = 0,
	limit: int = 50,
) -> dict:
	vendors, total = vendor_repo.list_vendors(db=db, search=search, category=category, skip=skip, limit=limit)
	vendor_ids = [vendor.vendor_id for vendor in vendors]

	order_counts = vendor_repo.get_order_count_by_vendor_ids(db=db, vendor_ids=vendor_ids)
	performance_map = vendor_repo.get_performance_by_vendor_ids(db=db, vendor_ids=vendor_ids)
	material_counts = vendor_repo.get_material_count_by_vendor_ids(db=db, vendor_ids=vendor_ids)
	preferred_vendor_ids = vendor_repo.get_preferred_vendor_ids(db=db, vendor_ids=vendor_ids)

	items = []
	for vendor in vendors:
		perf = performance_map.get(vendor.vendor_id)
		ai_score = _compute_ai_score(perf)
		on_time_pct = float(perf.on_time_delivery_pct) if perf and perf.on_time_delivery_pct is not None else None
		quality_score = float(perf.quality_score) if perf and perf.quality_score is not None else None
		defect_rate = float(perf.defect_rate_pct) if perf and perf.defect_rate_pct is not None else None

		rating = _round((quality_score or 0.0) / 2.0, 1) if quality_score is not None else None
		ai_recommended = bool(
			(ai_score or 0.0) >= 75.0
			and (on_time_pct or 0.0) >= 90.0
			and (defect_rate or 0.0) <= 1.0
		)

		items.append(
			{
				"vendor_id": vendor.vendor_id,
				"vendor_name": vendor.vendor_name,
				"rating": rating,
				"performance_pct": _round(on_time_pct, 1),
				"location": _build_location(vendor.city, vendor.state, vendor.country),
				"email": vendor.email,
				"category": vendor.category,
				"past_orders_count": int(order_counts.get(vendor.vendor_id, 0)),
				"materials_supplied_count": int(material_counts.get(vendor.vendor_id, 0)),
				"preferred_vendor": vendor.vendor_id in preferred_vendor_ids,
				"ai_recommended": ai_recommended,
				"ai_score": _round(ai_score, 1),
			}
		)

	return success_response(
		data={
			"total": total,
			"items": items,
		},
		message="Vendor cards fetched successfully.",
	)


async def get_vendor_profile(db: Session, vendor_id: str) -> dict:
	vendor = vendor_repo.get_vendor_by_id(db=db, vendor_id=vendor_id)
	if not vendor:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"Vendor '{vendor_id}' not found.",
		)

	deals = vendor_repo.get_purchase_history_by_vendor_id(db=db, vendor_id=vendor_id)
	performance = vendor_repo.get_vendor_performance_by_vendor_id(db=db, vendor_id=vendor_id)
	contracts = vendor_repo.get_contracts_by_vendor_id(db=db, vendor_id=vendor_id)
	materials = vendor_repo.get_material_map_by_vendor_id(db=db, vendor_id=vendor_id)

	unit_prices = [float(deal.unit_price) for deal in deals if deal.unit_price is not None]
	avg_price = _average(unit_prices)

	delivery_times = [value for value in (_delivery_time_days(deal) for deal in deals) if value is not None]
	average_delivery_time = _average(delivery_times)

	total_orders = len(deals)
	computed_avg_delay = _average([_delay_days(deal) for deal in deals])
	if computed_avg_delay is None and performance:
		computed_avg_delay = float(performance.avg_delay_days or 0.0)
	avg_delay_days = float(computed_avg_delay or 0.0)
	on_time_pct = float(performance.on_time_delivery_pct) if performance and performance.on_time_delivery_pct is not None else None
	quality_score = float(performance.quality_score) if performance and performance.quality_score is not None else None
	defect_rate_pct = float(performance.defect_rate_pct) if performance and performance.defect_rate_pct is not None else None
	ai_score = _compute_ai_score(performance)

	preferred_vendor = any(item.preferred_vendor_id == vendor_id for item in materials)

	contract_items = []
	active_contracts = 0
	expiring_contracts = 0
	expired_contracts = 0
	for contract in contracts:
		computed_status = _derive_contract_status(contract.end_date, contract.status)
		if computed_status == "Active":
			active_contracts += 1
		elif computed_status == "Expiring":
			expiring_contracts += 1
		else:
			expired_contracts += 1

		contract_items.append(
			{
				"contract_id": contract.contract_id,
				"contract_type": contract.contract_type,
				"start_date": contract.start_date.isoformat() if contract.start_date else None,
				"end_date": contract.end_date.isoformat() if contract.end_date else None,
				"agreed_pricing": contract.negotiated_rate,
				"contract_value": _round(contract.contract_value, 2),
				"status": computed_status,
				"payment_terms": contract.payment_terms,
				"auto_renew": bool(contract.auto_renew),
			}
		)

	materials_items = []
	for material in materials:
		matched_deals = _material_deals(deals=deals, material_description=material.material_description)
		quantities = [float(item.quantity) for item in matched_deals if item.quantity is not None]
		lead_times = [
			value
			for value in (
				(item.delivery_date - item.po_date).days if item.delivery_date and item.po_date else None
				for item in matched_deals
			)
			if value is not None
		]

		vendor_role = "secondary"
		if material.primary_vendor_id == vendor_id:
			vendor_role = "primary"
		elif material.preferred_vendor_id == vendor_id:
			vendor_role = "preferred"

		materials_items.append(
			{
				"material_code": material.material_code,
				"material_name": material.material_description,
				"category": material.category,
				"vendor_role": vendor_role,
				"capacity_per_material": _round(max(quantities), 2) if quantities else None,
				"lead_time_days": _round(_average([float(day) for day in lead_times]), 1) if lead_times else None,
				"contract_available": bool(material.contract_available),
			}
		)

	risk = _risk_indicator(defect_rate_pct=defect_rate_pct, avg_delay_days=avg_delay_days)
	material_contract_available = any(item["contract_available"] for item in materials_items)
	contract_available_for_skip_rfq = active_contracts > 0 or material_contract_available

	strengths = []
	if (on_time_pct or 0.0) >= 95.0:
		strengths.append("High on-time delivery")
	if (quality_score or 0.0) >= 8.5:
		strengths.append("Strong quality score")
	if (defect_rate_pct or 0.0) <= 0.5:
		strengths.append("Low defect rate")
	if active_contracts > 0:
		strengths.append("Active contract available for skip-RFQ")

	risks = []
	if (defect_rate_pct or 0.0) > 1.0:
		risks.append("Increasing defect rate")
	if (avg_delay_days or 0.0) > 3.0:
		risks.append("Delivery delays observed")
	if expiring_contracts > 0:
		risks.append("Contract expiring soon")
	if active_contracts == 0:
		risks.append("No active contract available")

	recommendation = _recommendation(
		preferred_vendor=preferred_vendor,
		ai_score=ai_score,
		on_time_delivery_pct=on_time_pct,
		defect_rate_pct=defect_rate_pct,
		risk_level=risk["level"],
		active_contracts=active_contracts,
	)

	recent_transactions = []
	for deal in deals[:5]:
		recent_transactions.append(
			{
				"deal_id": deal.deal_id,
				"po_number": deal.po_number,
				"material_or_service": deal.material_or_service,
				"quantity": _round(deal.quantity, 2),
				"unit": deal.unit,
				"unit_price": _round(deal.unit_price, 2),
				"total_value": _round(deal.total_value, 2),
				"po_date": deal.po_date.isoformat() if deal.po_date else None,
				"delivery_date": deal.delivery_date.isoformat() if deal.delivery_date else None,
				"actual_delivery": deal.actual_delivery.isoformat() if deal.actual_delivery else None,
				"status": deal.status,
			}
		)

	profile_payload = {
		"vendor_master": {
			"vendor_id": vendor.vendor_id,
			"vendor_name": vendor.vendor_name,
			"rating": _round((quality_score or 0.0) / 2.0, 1) if quality_score is not None else None,
			"performance_pct": _round(on_time_pct, 1),
			"location": _build_location(vendor.city, vendor.state, vendor.country),
			"contact_info": {
				"contact_person": vendor.contact_person,
				"phone": vendor.phone,
				"email": vendor.email,
			},
			"preferred_vendor": preferred_vendor,
			"category": vendor.category,
			"sub_category": vendor.sub_category,
		},
		"summary_metrics": {
			"total_orders": total_orders,
			"active_contracts": active_contracts,
			"materials_supplied": len(materials_items),
			"ai_score": _round(ai_score, 1),
			"average_price": _round(avg_price, 2),
			"average_delivery_time_days": _round(average_delivery_time, 1),
			"risk_indicator": risk,
			"contract_available_for_skip_rfq": contract_available_for_skip_rfq,
		},
		"past_deals": {
			"total_orders": total_orders,
			"average_price": _round(avg_price, 2),
			"delivery_performance_pct": _round(on_time_pct, 1),
			"average_delivery_time_days": _round(average_delivery_time, 1),
			"recent_transactions": recent_transactions,
		},
		"performance_scorecard": {
			"on_time_delivery_pct": _round(on_time_pct, 1),
			"quality_score": _round(quality_score, 2),
			"defect_rate_pct": _round(defect_rate_pct, 2),
			"avg_delay_days": _round(avg_delay_days, 2),
			"ai_score": _round(ai_score, 1),
		},
		"contracts": {
			"active_contracts": active_contracts,
			"expiring_contracts": expiring_contracts,
			"expired_contracts": expired_contracts,
			"items": contract_items,
		},
		"materials": {
			"count": len(materials_items),
			"items": materials_items,
		},
		"ai_insights": {
			"strengths": strengths,
			"risks": risks,
			"recommendation": recommendation,
		},
	}

	return success_response(
		data=profile_payload,
		message=f"Vendor profile for '{vendor_id}' fetched successfully.",
	)
