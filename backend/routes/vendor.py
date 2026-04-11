"""
Vendor Routes
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.services import vendor_service

router = APIRouter(
	prefix="/vendors",
	tags=["Vendors"],
)


@router.get(
	"",
	summary="List vendors for cards",
	description="Returns vendor cards with rating, performance, location, and past order counts.",
)
async def list_vendors(
	search: Optional[str] = Query(default=None, description="Search by vendor id, name, city, or email"),
	category: Optional[str] = Query(default=None, description="Filter by vendor category"),
	skip: int = Query(default=0, ge=0, description="Number of records to skip"),
	limit: int = Query(default=50, ge=1, le=200, description="Max records to return"),
	db: Session = Depends(get_db),
):
	return await vendor_service.list_vendor_cards(
		db=db,
		search=search,
		category=category,
		skip=skip,
		limit=limit,
	)


@router.get(
	"/{vendor_id}/profile",
	summary="Get complete vendor profile",
	description=(
		"Aggregates vendor master, deals, performance, contracts, and material mapping "
		"into a UI-ready detail payload."
	),
)
async def get_vendor_profile(vendor_id: str, db: Session = Depends(get_db)):
	return await vendor_service.get_vendor_profile(db=db, vendor_id=vendor_id)


@router.get(
	"/{vendor_id}",
	summary="Get vendor profile (alias)",
	description="Compatibility alias for /vendors/{vendor_id}/profile.",
)
async def get_vendor_profile_alias(vendor_id: str, db: Session = Depends(get_db)):
	return await vendor_service.get_vendor_profile(db=db, vendor_id=vendor_id)
