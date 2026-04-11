"""
Bid Routes
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.schemas.bid_schema import BidSubmitRequest, VendorSelectRequest
from backend.services import bid_service

router = APIRouter(
	prefix="/bid",
	tags=["Bids"],
)


@router.post(
	"/rfq/{rfq_id}/submit",
	summary="Submit or update vendor bid",
	description="Submits vendor bid and refreshes normalized evaluation for real-time frontend updates.",
)
async def submit_bid(rfq_id: str, payload: BidSubmitRequest, db: Session = Depends(get_db)):
	return await bid_service.submit_bid(db=db, rfq_id=rfq_id, payload=payload)


@router.post(
	"/rfq/{rfq_id}/evaluate",
	summary="Evaluate bids for RFQ",
	description="Evaluates bids only for RFQs in Open status and returns bids/evaluation/ai_insights.",
)
async def evaluate_bids(rfq_id: str, db: Session = Depends(get_db)):
	return await bid_service.evaluate_bids(db=db, rfq_id=rfq_id)


@router.get(
	"/rfq/{rfq_id}/live",
	summary="Get live bid evaluation snapshot",
)
async def get_live_evaluation(rfq_id: str, db: Session = Depends(get_db)):
	return await bid_service.get_live_evaluation(db=db, rfq_id=rfq_id)


@router.post(
	"/rfq/{rfq_id}/select",
	summary="Select vendor and close RFQ",
	description="Selects winning vendor from evaluated bids and closes RFQ.",
)
async def select_vendor(rfq_id: str, payload: VendorSelectRequest, db: Session = Depends(get_db)):
	return await bid_service.select_vendor_and_close_rfq(
		db=db,
		rfq_id=rfq_id,
		vendor_id=payload.vendor_id,
	)
