"""
RFQ Routes
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.schemas.rfq_schema import (
	RFQManualCreateRequest,
	RFQPublicVendorRegisterRequest,
	RFQSendRequest,
	RFQUpdateRequest,
)
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


@router.post(
	"/manual",
	summary="Create RFQ draft manually",
	description="Creates RFQ directly in Draft state from RFQ/Tender module input.",
)
async def create_manual_rfq(payload: RFQManualCreateRequest, db: Session = Depends(get_db)):
	return await rfq_service.create_manual_rfq(db=db, payload=payload)


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


@router.put(
	"/{rfq_id}",
	summary="Edit RFQ",
	description="Updates RFQ while in internal stages (Draft/Published).",
)
async def update_rfq(rfq_id: str, payload: RFQUpdateRequest, db: Session = Depends(get_db)):
	return await rfq_service.update_rfq(db=db, rfq_id=rfq_id, payload=payload)


@router.delete(
	"/{rfq_id}",
	summary="Delete RFQ",
	description="Deletes RFQ and linked distribution/bid records for Draft, Published, or Open statuses.",
)
async def delete_rfq(rfq_id: str, db: Session = Depends(get_db)):
	return await rfq_service.delete_rfq(db=db, rfq_id=rfq_id)


@router.get(
	"/{rfq_id}/vendors/recommended",
	summary="Get recommended vendors for RFQ",
	description="Returns vendors filtered by material relevance, performance, and active availability.",
)
async def get_recommended_vendors(rfq_id: str, db: Session = Depends(get_db)):
	return await rfq_service.get_recommended_vendors(db=db, rfq_id=rfq_id)


@router.post(
	"/{rfq_id}/publish",
	summary="Open RFQ for bidding",
	description="Transitions RFQ from Published to Open for Bidding and generates public link.",
)
async def publish_rfq(rfq_id: str, db: Session = Depends(get_db)):
	return await rfq_service.publish_rfq(db=db, rfq_id=rfq_id)


@router.post(
	"/{rfq_id}/open-for-bidding",
	summary="Open RFQ for bidding (alias)",
	description="Alias endpoint to open RFQ in vendor portal/public bidding mode.",
)
async def open_rfq_for_bidding(rfq_id: str, db: Session = Depends(get_db)):
	return await rfq_service.open_rfq_for_bidding(db=db, rfq_id=rfq_id)


@router.post(
	"/{rfq_id}/send",
	summary="Send RFQ to relevant vendors",
	description="Validates RFQ completeness, publishes from Draft, and sends notifications to relevant vendors.",
)
async def send_rfq_to_vendors(rfq_id: str, payload: RFQSendRequest, db: Session = Depends(get_db)):
	return await rfq_service.send_rfq_to_vendors(db=db, rfq_id=rfq_id, vendor_ids=payload.vendor_ids)


@router.get(
	"/{rfq_id}/distributions",
	summary="Get RFQ distribution history",
)
async def get_rfq_distribution_history(rfq_id: str, db: Session = Depends(get_db)):
	return await rfq_service.list_rfq_distributions(db=db, rfq_id=rfq_id)


@router.get(
	"/public/{rfq_id}",
	summary="Get public RFQ detail",
	description="Public RFQ endpoint for registered vendors and new vendor onboarding.",
)
async def get_public_rfq(
	rfq_id: str,
	vendor_id: Optional[str] = Query(default=None, description="Optional registered vendor id for bid action enablement."),
	db: Session = Depends(get_db),
):
	return await rfq_service.get_public_rfq(db=db, rfq_id=rfq_id, vendor_id=vendor_id)


@router.post(
	"/public/{rfq_id}/register",
	summary="Register public vendor for RFQ",
	description="Registers new vendor from public RFQ and returns bid submission action.",
)
async def register_public_vendor_for_rfq(
	rfq_id: str,
	payload: RFQPublicVendorRegisterRequest,
	db: Session = Depends(get_db),
):
	return await rfq_service.register_public_vendor_for_rfq(db=db, rfq_id=rfq_id, payload=payload)


@router.get(
	"/vendor-portal/open",
	summary="List open RFQs for vendor portal",
	description="Returns only Open for Bidding RFQs with submit-bid action and deadline validity.",
)
async def list_open_rfqs_for_vendor_portal(
	vendor_id: Optional[str] = Query(default=None, description="Optional vendor filter for invited RFQs."),
	db: Session = Depends(get_db),
):
	return await rfq_service.list_open_rfqs_for_vendor_portal(db=db, vendor_id=vendor_id)
