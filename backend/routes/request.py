"""
Purchase Request Routes
"""

import os
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.schemas.request_schema import PRCreate, PRUpdate, DescriptionRewriteRequest
from backend.services import request_service
from backend.repositories import request_repo

router = APIRouter(
    prefix="/purchase-request",
    tags=["Purchase Requests"],
)


@router.post(
    "/rewrite-description",
    summary="AI Rewrite Description",
    description="Rewrite description into a structured procurement-ready format and return missing details.",
)
async def rewrite_description(data: DescriptionRewriteRequest):
    return await request_service.rewrite_description(data)


@router.post(
    "/enhance-description",
    summary="AI Rewrite Description (Compatibility)",
    description="Compatibility alias for rewrite-description endpoint.",
)
async def enhance_description(data: DescriptionRewriteRequest):
    return await request_service.rewrite_description(data)


@router.post(
    "",
    summary="Create a new Purchase Request",
    description="Submit a procurement form and generate PR PDF using final form values.",
    status_code=status.HTTP_201_CREATED,
)
async def create_purchase_request(
    data: PRCreate,
    db: Session = Depends(get_db),
):
    return await request_service.create_purchase_request(db=db, data=data)


@router.get(
    "s",
    summary="List all Purchase Requests",
    description="Returns a paginated list of all purchase requests ordered by newest first.",
)
async def list_purchase_requests(
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=50, ge=1, le=200, description="Max records to return"),
    db: Session = Depends(get_db),
):
    return await request_service.list_purchase_requests(db=db, skip=skip, limit=limit)


@router.get(
    "/{pr_id}",
    summary="Get a Purchase Request by ID",
)
async def get_purchase_request(pr_id: str, db: Session = Depends(get_db)):
    return await request_service.get_purchase_request(db=db, pr_id=pr_id)


@router.put(
    "/{pr_id}",
    summary="Update a Purchase Request",
    description="Update fields on a PR. If printable fields change, a new PDF is generated.",
)
async def update_purchase_request(
    pr_id: str,
    data: PRUpdate,
    db: Session = Depends(get_db),
):
    return await request_service.update_purchase_request(db=db, pr_id=pr_id, data=data)


@router.get(
    "/{pr_id}/pdf",
    summary="Download PR PDF",
    description="Download the generated PDF for a Purchase Request.",
    response_class=FileResponse,
)
async def download_pr_pdf(pr_id: str, db: Session = Depends(get_db)):
    pr = request_repo.get_pr_by_id(db, pr_id)
    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase Request '{pr_id}' not found.",
        )
    if not pr.pdf_path or not os.path.exists(pr.pdf_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF not yet generated for this Purchase Request.",
        )
    return FileResponse(
        path=pr.pdf_path,
        media_type="application/pdf",
        filename=f"{pr.pr_number}.pdf",
    )
