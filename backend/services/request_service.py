"""
Purchase Request Service — orchestrates AI validation, PDF generation, and DB persistence.
"""

from typing import Optional, Tuple
from sqlalchemy.orm import Session

from backend.schemas.request_schema import PRCreate, PRUpdate, PRResponse, PRListResponse, AIValidationResult
from backend.repositories import request_repo
from backend.models.request import PurchaseRequest
from backend.llm.chains.pr_validation_graph import run_pr_validation
from backend.services.pdf_service import generate_pr_pdf
from backend.utils.logger import get_logger
from backend.utils.response_formatter import success_response, error_response
from fastapi import HTTPException, status

logger = get_logger(__name__)


async def create_purchase_request(db: Session, data: PRCreate) -> dict:
    """
    Full flow:
      1. Run LangGraph AI validation
      2. Generate PDF
      3. Save PR to DB
      4. Return response with AI insights
    """
    logger.info("Creating purchase request: item=%s category=%s", data.item_name, data.category)

    # Step 1: AI Validation
    ai_result: AIValidationResult = await run_pr_validation(
        item_name=data.item_name,
        category=data.category,
        quantity=data.quantity,
        budget=data.budget,
        description=data.description,
    )

    # Step 2: Save to DB (need PR number before PDF)
    pr = request_repo.create_pr(db=db, data=data, ai_result=ai_result, pdf_path=None)

    # Step 3: Generate PDF
    try:
        pdf_path = generate_pr_pdf(
            pr_number=pr.pr_number,
            item_name=pr.item_name,
            category=pr.category,
            quantity=pr.quantity,
            budget=pr.budget,
            description=pr.description,
            improved_description=pr.improved_description,
            missing_fields=pr.missing_fields,
            budget_feedback=pr.budget_feedback,
            ai_status=pr.ai_status,
            created_at=pr.created_at,
        )
        # Update PR with PDF path
        pr = request_repo.update_pr(
            db=db,
            pr=pr,
            data=PRUpdate(),
            pdf_path=pdf_path,
        )
    except Exception as e:
        logger.error("PDF generation failed (non-fatal): %s", e)

    response_data = PRResponse.model_validate(pr)
    return success_response(
        data=response_data.model_dump(),
        message=f"Purchase Request {pr.pr_number} created successfully.",
    )


async def get_purchase_request(db: Session, pr_id: str) -> dict:
    pr = request_repo.get_pr_by_id(db, pr_id)
    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase Request with ID '{pr_id}' not found.",
        )
    return success_response(data=PRResponse.model_validate(pr).model_dump())


async def list_purchase_requests(db: Session, skip: int = 0, limit: int = 50) -> dict:
    items, total = request_repo.get_all_prs(db, skip=skip, limit=limit)
    list_data = PRListResponse(
        total=total,
        items=[PRResponse.model_validate(pr) for pr in items],
    )
    return success_response(data=list_data.model_dump())


async def update_purchase_request(db: Session, pr_id: str, data: PRUpdate) -> dict:
    """
    Update PR and re-run AI validation if any core fields changed.
    """
    pr = request_repo.get_pr_by_id(db, pr_id)
    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase Request with ID '{pr_id}' not found.",
        )

    # Merge updated fields with existing values for AI re-validation
    updated_fields = data.model_dump(exclude_unset=True)
    ai_fields = {"item_name", "category", "quantity", "budget", "description"}
    needs_ai_rerun = bool(set(updated_fields.keys()) & ai_fields)

    ai_result: Optional[AIValidationResult] = None
    if needs_ai_rerun:
        logger.info("Re-running AI validation after update on PR: %s", pr.pr_number)
        ai_result = await run_pr_validation(
            item_name=updated_fields.get("item_name", pr.item_name),
            category=updated_fields.get("category", pr.category),
            quantity=updated_fields.get("quantity", pr.quantity),
            budget=updated_fields.get("budget", pr.budget),
            description=updated_fields.get("description", pr.description),
        )

    pr = request_repo.update_pr(db=db, pr=pr, data=data, ai_result=ai_result)

    # Regenerate PDF if AI re-ran or core fields changed
    if needs_ai_rerun:
        try:
            pdf_path = generate_pr_pdf(
                pr_number=pr.pr_number,
                item_name=pr.item_name,
                category=pr.category,
                quantity=pr.quantity,
                budget=pr.budget,
                description=pr.description,
                improved_description=pr.improved_description,
                missing_fields=pr.missing_fields,
                budget_feedback=pr.budget_feedback,
                ai_status=pr.ai_status,
                created_at=pr.created_at,
            )
            pr = request_repo.update_pr(db=db, pr=pr, data=PRUpdate(), pdf_path=pdf_path)
        except Exception as e:
            logger.error("PDF regeneration failed (non-fatal): %s", e)

    return success_response(
        data=PRResponse.model_validate(pr).model_dump(),
        message=f"Purchase Request {pr.pr_number} updated successfully.",
    )
