"""
Bid Routes
"""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.schemas.bid_schema import BidManualOverrideRequest, SendForApprovalRequest, VendorSelectRequest
from backend.services import bid_service

router = APIRouter(
	prefix="/bid",
	tags=["Bids"],
)


def _require_internal_access(x_internal_access: Optional[str] = Header(default=None)) -> None:
	value = (x_internal_access or "").strip().lower()
	if value not in {"true", "1", "yes", "internal"}:
		raise HTTPException(
			status_code=status.HTTP_403_FORBIDDEN,
			detail="Internal access is required for this endpoint.",
		)


@router.post(
	"/rfq/{rfq_id}/submit",
	summary="Submit bid from Vendor Portal",
	description="Accepts vendor bid with required commercial fields and document uploads.",
)
async def submit_bid(
	rfq_id: str,
	vendor_id: str = Form(...),
	price: float = Form(...),
	currency: str = Form("INR"),
	lead_time: int = Form(...),
	delivery_schedule: str = Form(...),
	delivery_terms: str = Form(...),
	payment_terms: str = Form(...),
	validity: int = Form(...),
	specification_compliance: float = Form(...),
	alternative_product: Optional[str] = Form(default=None),
	quotation_pdf: UploadFile = File(...),
	technical_sheet: UploadFile = File(...),
	compliance_documents: UploadFile = File(...),
	certifications: UploadFile = File(...),
	db: Session = Depends(get_db),
):
	return await bid_service.submit_bid_with_documents(
		db=db,
		rfq_id=rfq_id,
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
		quotation_pdf=quotation_pdf,
		technical_sheet=technical_sheet,
		compliance_documents=compliance_documents,
		certifications=certifications,
	)


@router.get(
	"/rfq/{rfq_id}/submissions",
	summary="Get RFQ bid submissions (internal)",
	description="Returns vendor bids with document status for internal bid management.",
)
async def list_bid_submissions(
	rfq_id: str,
	db: Session = Depends(get_db),
	_: None = Depends(_require_internal_access),
):
	return await bid_service.list_bids_for_management(db=db, rfq_id=rfq_id)


@router.post(
	"/rfq/{rfq_id}/evaluate",
	summary="Evaluate bids for RFQ (internal)",
	description="Evaluates normalized bids only for Open for Bidding RFQs.",
)
async def evaluate_bids(
	rfq_id: str,
	db: Session = Depends(get_db),
	_: None = Depends(_require_internal_access),
):
	return await bid_service.evaluate_bids(db=db, rfq_id=rfq_id)


@router.get(
	"/rfq/{rfq_id}/live",
	summary="Get live bid evaluation snapshot (internal)",
)
async def get_live_evaluation(
	rfq_id: str,
	db: Session = Depends(get_db),
	_: None = Depends(_require_internal_access),
):
	return await bid_service.get_live_evaluation(db=db, rfq_id=rfq_id)


@router.post(
	"/rfq/{rfq_id}/manual-override",
	summary="Manual score override (internal)",
	description="Allows internal users to override computed vendor score or breakdown.",
)
async def manual_override(
	rfq_id: str,
	payload: BidManualOverrideRequest,
	db: Session = Depends(get_db),
	_: None = Depends(_require_internal_access),
):
	return await bid_service.manual_override_bid_evaluation(db=db, rfq_id=rfq_id, payload=payload)


@router.post(
	"/rfq/{rfq_id}/send-for-approval",
	summary="Send shortlisted vendor for approval (internal)",
	description="Sends top-ranked or selected vendor from shortlist for approval workflow.",
)
async def send_for_approval(
	rfq_id: str,
	payload: SendForApprovalRequest,
	db: Session = Depends(get_db),
	_: None = Depends(_require_internal_access),
):
	return await bid_service.send_for_approval(db=db, rfq_id=rfq_id, payload=payload)


@router.post(
	"/rfq/{rfq_id}/select",
	summary="Finalize vendor selection and close RFQ (internal)",
	description="Selects winning vendor from shortlist and closes RFQ.",
)
async def select_vendor(
	rfq_id: str,
	payload: VendorSelectRequest,
	db: Session = Depends(get_db),
	_: None = Depends(_require_internal_access),
):
	return await bid_service.select_vendor_and_close_rfq(
		db=db,
		rfq_id=rfq_id,
		vendor_id=payload.vendor_id,
	)
