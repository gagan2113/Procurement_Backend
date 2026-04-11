"""
RFQ Routes
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.schemas.rfq_schema import RFQSendRequest
from backend.services import rfq_service

router = APIRouter(
	prefix="/rfq",
	tags=["RFQ"],
)


@router.post(
	"/from-pr/{pr_id}",
	summary="Auto-create RFQ draft from approved PR",
	description="Creates RFQ in Draft state from an approved PR and returns immediate workflow actions.",
)
async def create_rfq_from_pr(pr_id: str, db: Session = Depends(get_db)):
	return await rfq_service.create_rfq_for_approved_pr(db=db, pr_id=pr_id)


@router.get(
	"",
	summary="List RFQs",
	description="Returns RFQ cards for dashboard/list pages with status, key details, and PDF visibility.",
)
async def list_rfqs(
	status: Optional[str] = Query(default=None, description="Optional RFQ status filter."),
	search: Optional[str] = Query(default=None, description="Optional search term for RFQ number, PR number, material, or category."),
	db: Session = Depends(get_db),
):
	return await rfq_service.list_rfqs(db=db, status_filter=status, search=search)


@router.get(
	"/{rfq_id}/pdf",
	summary="Download RFQ PDF",
	description="Returns the RFQ PDF document. If missing, it is generated on demand.",
)
async def download_rfq_pdf(rfq_id: str, db: Session = Depends(get_db)):
	pdf_path, filename = await rfq_service.get_rfq_pdf_file(db=db, rfq_id=rfq_id)
	return FileResponse(path=pdf_path, media_type="application/pdf", filename=filename)


@router.get(
	"/{rfq_id}",
	summary="Get RFQ detail",
)
async def get_rfq_detail(rfq_id: str, db: Session = Depends(get_db)):
	return await rfq_service.get_rfq_detail(db=db, rfq_id=rfq_id)


@router.get(
	"/{rfq_id}/vendors/recommended",
	summary="Get recommended vendors for RFQ",
	description="Returns vendors filtered by material relevance, performance, and active availability.",
)
async def get_recommended_vendors(rfq_id: str, db: Session = Depends(get_db)):
	return await rfq_service.get_recommended_vendors(db=db, rfq_id=rfq_id)


@router.post(
	"/{rfq_id}/publish",
	summary="Publish RFQ",
	description="Publishes RFQ to portal and transitions lifecycle from Draft to Open for Bidding.",
)
async def publish_rfq(rfq_id: str, db: Session = Depends(get_db)):
	return await rfq_service.publish_rfq(db=db, rfq_id=rfq_id)


@router.post(
	"/{rfq_id}/send",
	summary="Send RFQ to selected vendors",
	description="Sends RFQ via email and vendor portal notification for selected vendors.",
)
async def send_rfq_to_vendors(rfq_id: str, payload: RFQSendRequest, db: Session = Depends(get_db)):
	return await rfq_service.send_rfq_to_vendors(db=db, rfq_id=rfq_id, vendor_ids=payload.vendor_ids)


@router.get(
	"/{rfq_id}/distributions",
	summary="Get RFQ distribution history",
)
async def get_rfq_distribution_history(rfq_id: str, db: Session = Depends(get_db)):
	return await rfq_service.list_rfq_distributions(db=db, rfq_id=rfq_id)
