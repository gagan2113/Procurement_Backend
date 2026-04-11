"""
Purchase Request Service — handles AI rewrite, PDF generation, and DB persistence.
"""

import json
import re
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.config.constants import PRStatus
from backend.llm.llm_provider import get_llm
from backend.llm.prompt_templates import DESCRIPTION_REWRITE_PROMPT
from backend.repositories import request_repo
from backend.schemas.request_schema import (
    DescriptionRewriteRequest,
    DescriptionRewriteResponse,
    PRCreate,
    PRListResponse,
    PRResponse,
    PRUpdate,
)
from backend.services.pdf_service import generate_pr_pdf
from backend.services import rfq_service
from backend.utils.logger import get_logger
from backend.utils.response_formatter import success_response

logger = get_logger(__name__)


def _calculate_budget_per_unit(budget: float, quantity: int) -> Optional[float]:
    if quantity is None or quantity <= 0:
        return None
    try:
        return round(float(budget) / float(quantity), 2)
    except Exception:
        return None


def _to_pr_response(pr) -> dict:
    payload = PRResponse.model_validate(pr).model_dump()
    payload["budget_per_unit"] = _calculate_budget_per_unit(pr.budget, pr.quantity)
    return payload


def _clean_llm_json(text: str) -> str:
    cleaned = re.sub(r"```(?:json|text)?", "", text).replace("```", "").strip()
    return cleaned


def _sanitize_rewritten_description(text: str) -> str:
    """Remove non-requirement content like budget/timeline/priority/justification from rewrite output."""
    if not text:
        return text

    banned_sentence_patterns = [
        r"\bbudget\b",
        r"\bestimated[_\s-]*budget\b",
        r"\bINR\b|\bUSD\b|\$|₹",
        r"\bexpected\s+delivery\b",
        r"\bdelivery\s+date\b",
        r"\bdelivery\s+timeline\b",
        r"\bpriority\b",
        r"\bbusiness\s+justification\b",
        r"\bapproval\b",
    ]

    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    kept = []
    for sentence in sentences:
        if not sentence:
            continue
        lower_sentence = sentence.lower()
        if any(re.search(pattern, lower_sentence, flags=re.IGNORECASE) for pattern in banned_sentence_patterns):
            continue
        kept.append(sentence)

    sanitized = " ".join(kept).strip()
    return sanitized


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def _is_technical_context(data: DescriptionRewriteRequest) -> bool:
    category = (data.category or "").lower()
    description = (data.description or "").lower()
    category_hit = any(k in category for k in ["it", "hardware", "software", "technical", "electronics", "device"])
    description_hit = any(k in description for k in [
        "ram", "storage", "ssd", "hdd", "wifi", "wi-fi", "lte", "processor", "cpu", "display", "tablet", "laptop",
    ])
    return category_hit or description_hit


def _expand_rewrite_if_short(text: str, data: DescriptionRewriteRequest) -> str:
    base = (text or "").strip()
    if _word_count(base) >= 110:
        return base

    common_extension = (
        "The requirement should clearly define acceptable product or service quality, reliability expectations, "
        "and fit-for-purpose performance in day-to-day operations. Vendors should provide standardized, market-available "
        "configurations aligned with the stated need, along with clear documentation for technical details, compliance, "
        "and support commitments where relevant."
    )

    if _is_technical_context(data):
        category_extension = (
            "For technical suitability, the proposed configuration should ensure stable performance under routine workload, "
            "compatibility with commonly used enterprise environments, and dependable connectivity for operational continuity. "
            "Responses should clarify operating environment support, expected device reliability, maintainability, and warranty/service coverage."
        )
    elif "furniture" in (data.category or "").lower():
        category_extension = (
            "For physical design and usability, proposals should describe build quality, material durability, ergonomic comfort, "
            "and dimensional suitability for the intended workspace. Vendors should also mention finish quality and maintenance practicality "
            "to support long-term use in professional environments."
        )
    elif "service" in (data.category or "").lower():
        category_extension = (
            "For service-oriented requirements, vendor responses should define scope boundaries, measurable deliverables, "
            "quality checkpoints, and execution methodology. The service model should include clear accountability, reporting standards, "
            "and consistency in service quality over the engagement lifecycle."
        )
    elif "machinery" in (data.category or "").lower() or "machine" in (data.category or "").lower():
        category_extension = (
            "For operational equipment, proposals should specify functional capability, throughput expectations, "
            "performance reliability, and applicable safety/compliance adherence. Vendors should outline operating suitability, "
            "maintenance considerations, and supportability for sustained usage."
        )
    else:
        category_extension = (
            "Proposals should provide a complete and practical specification profile including functional suitability, "
            "quality expectations, and relevant performance characteristics commonly required for this procurement type."
        )

    enriched = f"{base} {common_extension} {category_extension}".strip()
    return enriched


def _fallback_missing_details(data: DescriptionRewriteRequest) -> list[str]:
    details = []
    description = (data.description or "").lower()
    category = (data.category or "").lower()

    if len(description) < 40:
        details.append("Add more detailed functional and specification requirements")

    if "furniture" in category:
        if "material" not in description:
            details.append("Specify preferred material and finish")
        if not any(k in description for k in ["dimension", "size", "height", "width", "depth"]):
            details.append("Add dimension or size requirements")
        if "durability" not in description and "durable" not in description:
            details.append("Define durability or load-bearing expectations")

    if "service" in category:
        if "scope" not in description:
            details.append("Define scope of work clearly")
        if "deliverable" not in description:
            details.append("Define scope of work and expected deliverables")
        if "quality" not in description and "sla" not in description and "service level" not in description:
            details.append("Specify service quality expectations or service levels")

    if "machinery" in category:
        if "capacity" not in description:
            details.append("Mention required capacity")
        if "performance" not in description:
            details.append("Add performance criteria")
        if "safety" not in description and "compliance" not in description:
            details.append("Specify safety or compliance standards")

    if "it" in category or "hardware" in category or "software" in category or "technical" in category:
        if "config" not in description and "configuration" not in description and "spec" not in description:
            details.append("Clarify configuration and technical specifications")
        if "compatibility" not in description:
            details.append("Mention compatibility or integration requirements")
        if "performance" not in description:
            details.append("Define expected performance criteria")

    if not details:
        details.extend([
            "Clarify technical or functional specifications",
            "Specify quality or compliance expectations",
            "Add warranty or support requirements if applicable",
        ])

    # Keep output concise and user-actionable.
    deduped = []
    for item in details:
        if item not in deduped:
            deduped.append(item)
    return deduped[:5]


def _fallback_rewrite(data: DescriptionRewriteRequest) -> str:
    parts = []

    if data.item_name:
        parts.append(f"Procurement request for {data.item_name}")
    else:
        parts.append("Procurement request")

    if data.category:
        parts.append(f"under {data.category} category")

    sentence_1 = " ".join(parts).strip()

    sentence_2 = data.description.strip()
    if sentence_2 and not sentence_2.endswith((".", "!", "?")):
        sentence_2 = f"{sentence_2}."

    sentence_3 = (
        "Vendors should provide compliant options that meet functional needs, quality standards, "
        "performance expectations, and suitability for intended use."
    )
    sentence_4 = (
        "Responses should clearly explain configuration details, material or component quality as applicable, "
        "operational reliability, and support commitments relevant to the procurement category."
    )
    sentence_5 = (
        "Any assumptions should be explicitly stated, and proposals should align with standard market-available options "
        "that satisfy the requirement without ambiguity."
    )

    draft = " ".join(s for s in [sentence_1, sentence_2, sentence_3, sentence_4, sentence_5] if s).strip()
    return _expand_rewrite_if_short(draft, data)


def _parse_rewrite_output(raw_text: str, request_data: DescriptionRewriteRequest) -> DescriptionRewriteResponse:
    cleaned = _clean_llm_json(raw_text)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return DescriptionRewriteResponse(
            rewritten_description=_fallback_rewrite(request_data),
            missing_details=_fallback_missing_details(request_data),
        )

    rewritten_description = str(parsed.get("rewritten_description", "")).strip()
    if not rewritten_description:
        rewritten_description = _fallback_rewrite(request_data)
    rewritten_description = _sanitize_rewritten_description(rewritten_description)
    if not rewritten_description:
        rewritten_description = _fallback_rewrite(request_data)
    rewritten_description = _expand_rewrite_if_short(rewritten_description, request_data)
    rewritten_description = _sanitize_rewritten_description(rewritten_description) or _fallback_rewrite(request_data)

    raw_missing = parsed.get("missing_details", [])
    if isinstance(raw_missing, list):
        missing_details = [str(item).strip() for item in raw_missing if str(item).strip()]
    elif raw_missing:
        missing_details = [str(raw_missing).strip()]
    else:
        missing_details = []

    if not missing_details:
        missing_details = _fallback_missing_details(request_data)

    return DescriptionRewriteResponse(
        rewritten_description=rewritten_description,
        missing_details=missing_details,
    )


async def rewrite_description(data: DescriptionRewriteRequest) -> dict:
    """Rewrite description on-demand. Frontend can overwrite the current description field."""
    try:
        llm = get_llm()
        chain = DESCRIPTION_REWRITE_PROMPT | llm
        response = chain.invoke({
            "item_name": data.item_name or "Not provided",
            "category": data.category or "Not provided",
            "description": data.description,
        })
        output = _parse_rewrite_output(response.content, data)
    except Exception as exc:
        logger.error("Description rewrite failed: %s", exc)
        output = DescriptionRewriteResponse(
            rewritten_description=_fallback_rewrite(data),
            missing_details=_fallback_missing_details(data),
        )

    return success_response(
        data=output.model_dump(),
        message="Description rewritten successfully.",
    )


async def create_purchase_request(db: Session, data: PRCreate) -> dict:
    """
    Full flow:
      1. Save PR to DB using current description value
      2. Generate PDF with delivery date and budget per unit
      3. Return saved record
    """
    logger.info("Creating purchase request: item=%s category=%s", data.item_name, data.category)

    pr = request_repo.create_pr(db=db, data=data, ai_result=None, pdf_path=None)

    try:
        pdf_path = generate_pr_pdf(
            pr_number=pr.pr_number,
            item_name=pr.item_name,
            category=pr.category,
            quantity=pr.quantity,
            budget=pr.budget,
            budget_per_unit=_calculate_budget_per_unit(pr.budget, pr.quantity),
            expected_delivery_date=pr.expected_delivery_date,
            description=pr.description,
            created_at=pr.created_at,
        )
        pr = request_repo.update_pr(
            db=db,
            pr=pr,
            data=PRUpdate(),
            pdf_path=pdf_path,
        )
    except Exception as exc:
        logger.error("PDF generation failed (non-fatal): %s", exc)

    return success_response(
        data=_to_pr_response(pr),
        message=f"Purchase Request {pr.pr_number} created successfully.",
    )


async def get_purchase_request(db: Session, pr_id: str) -> dict:
    pr = request_repo.get_pr_by_id(db, pr_id)
    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase Request with ID '{pr_id}' not found.",
        )
    return success_response(data=_to_pr_response(pr))


async def list_purchase_requests(db: Session, skip: int = 0, limit: int = 50) -> dict:
    items, total = request_repo.get_all_prs(db, skip=skip, limit=limit)
    list_data = PRListResponse(
        total=total,
        items=[PRResponse.model_validate({**_to_pr_response(pr)}) for pr in items],
    )
    return success_response(data=list_data.model_dump())


async def update_purchase_request(db: Session, pr_id: str, data: PRUpdate) -> dict:
    """Update PR and regenerate PDF when printable fields change."""
    pr = request_repo.get_pr_by_id(db, pr_id)
    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase Request with ID '{pr_id}' not found.",
        )

    updated_fields = data.model_dump(exclude_unset=True)
    printable_fields = {
        "item_name",
        "category",
        "quantity",
        "budget",
        "expected_delivery_date",
        "description",
    }
    needs_pdf_regen = bool(set(updated_fields.keys()) & printable_fields)

    previous_status = pr.status
    pr = request_repo.update_pr(db=db, pr=pr, data=data, ai_result=None)

    if needs_pdf_regen:
        try:
            pdf_path = generate_pr_pdf(
                pr_number=pr.pr_number,
                item_name=pr.item_name,
                category=pr.category,
                quantity=pr.quantity,
                budget=pr.budget,
                budget_per_unit=_calculate_budget_per_unit(pr.budget, pr.quantity),
                expected_delivery_date=pr.expected_delivery_date,
                description=pr.description,
                created_at=pr.created_at,
            )
            pr = request_repo.update_pr(db=db, pr=pr, data=PRUpdate(), pdf_path=pdf_path)
        except Exception as exc:
            logger.error("PDF regeneration failed (non-fatal): %s", exc)

    response_payload = _to_pr_response(pr)

    if data.status == PRStatus.APPROVED and previous_status != PRStatus.APPROVED.value:
        rfq_workflow = await rfq_service.auto_create_rfq_for_approved_pr(db=db, pr=pr)
        response_payload["rfq_workflow"] = rfq_workflow

    return success_response(
        data=response_payload,
        message=f"Purchase Request {pr.pr_number} updated successfully.",
    )
