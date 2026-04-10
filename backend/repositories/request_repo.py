import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy.orm import Session

from backend.models.request import PurchaseRequest
from backend.schemas.request_schema import PRCreate, PRUpdate, AIValidationResult
from backend.config.constants import PR_NUMBER_PREFIX, AIStatus
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def _generate_pr_number(db: Session) -> str:
    """Generate a unique PR number in format PR-YYYYMMDD-XXXX."""
    today = datetime.utcnow().strftime("%Y%m%d")
    prefix = f"{PR_NUMBER_PREFIX}-{today}-"
    count = db.query(PurchaseRequest).filter(
        PurchaseRequest.pr_number.like(f"{prefix}%")
    ).count()
    return f"{prefix}{(count + 1):04d}"


def create_pr(
    db: Session,
    data: PRCreate,
    ai_result: Optional[AIValidationResult] = None,
    pdf_path: Optional[str] = None,
) -> PurchaseRequest:
    pr_number = _generate_pr_number(db)
    pr = PurchaseRequest(
        id=str(uuid.uuid4()),
        pr_number=pr_number,
        item_name=data.item_name,
        category=data.category,
        quantity=data.quantity,
        budget=data.budget,
        expected_delivery_date=data.expected_delivery_date,
        description=data.description,
        improved_description=ai_result.improved_description if ai_result else None,
        missing_fields=ai_result.missing_fields if ai_result else [],
        budget_feedback=ai_result.budget_feedback if ai_result else None,
        ai_status=ai_result.status.value if ai_result else AIStatus.PENDING.value,
        pdf_path=pdf_path,
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)
    logger.info("Created PR: %s | id=%s", pr.pr_number, pr.id)
    return pr


def get_pr_by_id(db: Session, pr_id: str) -> Optional[PurchaseRequest]:
    return db.query(PurchaseRequest).filter(PurchaseRequest.id == pr_id).first()


def get_all_prs(
    db: Session,
    skip: int = 0,
    limit: int = 50,
) -> tuple[List[PurchaseRequest], int]:
    query = db.query(PurchaseRequest)
    total = query.count()
    items = query.order_by(PurchaseRequest.created_at.desc()).offset(skip).limit(limit).all()
    return items, total


def update_pr(
    db: Session,
    pr: PurchaseRequest,
    data: PRUpdate,
    ai_result: Optional[AIValidationResult] = None,
    pdf_path: Optional[str] = None,
) -> PurchaseRequest:
    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if hasattr(pr, field):
            # Convert enum to value if needed
            setattr(pr, field, value.value if hasattr(value, "value") else value)

    if ai_result:
        pr.improved_description = ai_result.improved_description
        pr.missing_fields = ai_result.missing_fields
        pr.budget_feedback = ai_result.budget_feedback
        pr.ai_status = ai_result.status.value

    if pdf_path:
        pr.pdf_path = pdf_path

    pr.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(pr)
    logger.info("Updated PR: %s | id=%s", pr.pr_number, pr.id)
    return pr
