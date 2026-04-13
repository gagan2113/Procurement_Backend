from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class BidSubmitRequest(BaseModel):
	vendor_id: str = Field(..., min_length=3, max_length=50)
	price: float = Field(..., gt=0)
	currency: str = Field(default="INR", min_length=3, max_length=10)
	lead_time: int = Field(..., ge=1)
	delivery_schedule: str = Field(..., min_length=3, max_length=2000)
	delivery_terms: str = Field(..., min_length=3, max_length=2000)
	payment_terms: str = Field(..., min_length=3, max_length=2000)
	validity: int = Field(..., ge=1, description="Bid validity in days")
	specification_compliance: float = Field(..., ge=0, le=100)
	alternative_product: Optional[str] = Field(default=None, max_length=2000)


class BidManualOverrideRequest(BaseModel):
	vendor_id: str = Field(..., min_length=3, max_length=50)
	score: Optional[float] = Field(default=None, ge=0, le=100)
	recommendation: Optional[str] = Field(default=None, max_length=50)
	breakdown: Optional[Dict[str, float]] = Field(default=None)


class SendForApprovalRequest(BaseModel):
	vendor_id: Optional[str] = Field(default=None, min_length=3, max_length=50)
	notes: Optional[str] = Field(default=None, max_length=1000)


class VendorSelectRequest(BaseModel):
	vendor_id: str = Field(..., min_length=3, max_length=50)


class BidOutput(BaseModel):
	bid_id: str
	rfq_id: str
	vendor_id: str
	vendor_name: str
	price: float
	currency: str
	lead_time: int
	delivery_schedule: str
	delivery_terms: str
	payment_terms: str
	validity: int
	specification_compliance: float
	alternative_product: Optional[str] = None
	document_status: str
	document_summary: Optional[str] = None
	document_compliance_score: Optional[float] = None
	quotation_pdf: Optional[str] = None
	technical_sheet: Optional[str] = None
	compliance_documents: Optional[str] = None
	certifications: Optional[str] = None
	normalized_price: Optional[float] = None
	normalized_delivery: Optional[float] = None
	normalized_quality: Optional[float] = None
	status: str
	updated_at: datetime


class EvaluationOutput(BaseModel):
	vendor_id: str
	vendor_name: str
	score: float
	rank: int
	breakdown: Dict[str, float]
	recommendation: str
	manual_override: bool = False


class AIInsightVendorOutput(BaseModel):
	vendor_name: str
	strengths: List[str]
	risks: List[str]
	recommendation: str
	risk_indicators: List[str] = Field(default_factory=list)


class BidEvaluationBundle(BaseModel):
	bids: List[BidOutput]
	evaluation: List[EvaluationOutput]
	ai_insights: Dict[str, AIInsightVendorOutput]
