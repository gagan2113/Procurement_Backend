from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class BidSubmitRequest(BaseModel):
	vendor_id: str = Field(..., min_length=3, max_length=50)
	quoted_price: float = Field(..., gt=0)
	currency: str = Field(default="INR", min_length=3, max_length=10)
	quoted_delivery_days: int = Field(..., ge=1)
	technical_compliance_pct: float = Field(..., ge=0, le=100)
	quality_commitment_score: float = Field(..., ge=0, le=10)
	warranty_months: int = Field(default=0, ge=0)
	payment_terms_days: Optional[int] = Field(default=None, ge=0)
	notes: Optional[str] = Field(default=None, max_length=2000)


class VendorSelectRequest(BaseModel):
	vendor_id: str = Field(..., min_length=3, max_length=50)


class BidOutput(BaseModel):
	bid_id: str
	rfq_id: str
	vendor_id: str
	vendor_name: str
	quoted_price: float
	currency: str
	quoted_delivery_days: int
	technical_compliance_pct: float
	quality_commitment_score: float
	warranty_months: int
	payment_terms_days: Optional[int] = None
	normalized_price: Optional[float] = None
	normalized_delivery: Optional[float] = None
	normalized_quality: Optional[float] = None
	status: str
	updated_at: datetime


class EvaluationOutput(BaseModel):
	bid_id: str
	vendor_id: str
	vendor_name: str
	price_score: float
	delivery_score: float
	quality_score: float
	risk_score: float
	final_score: float
	rank: int
	recommendation: str
	is_selected: bool


class AIInsightVendorOutput(BaseModel):
	vendor_name: str
	strengths: List[str]
	risks: List[str]
	recommendation: str


class BidEvaluationBundle(BaseModel):
	bids: List[BidOutput]
	evaluation: List[EvaluationOutput]
	ai_insights: Dict[str, AIInsightVendorOutput]
