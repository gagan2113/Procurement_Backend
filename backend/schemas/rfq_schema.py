from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class RFQActionResponse(BaseModel):
    rfq_id: str
    rfq_number: str
    status: str
    actions_available: List[str]


class RecommendedVendor(BaseModel):
    vendor_id: str
    vendor_name: str
    email: Optional[str] = None
    performance_score: Optional[float] = None
    past_orders_count: int
    preferred_tag: bool
    high_performing: bool
    active_vendor: bool


class RFQAutoCreateResponse(BaseModel):
    rfq_id: str
    rfq_number: str
    status: str
    actions_available: List[str]
    vendor_recommendations: List[RecommendedVendor]


class RFQDetailResponse(BaseModel):
    rfq_id: str
    rfq_number: str
    status: str
    pr_id: str
    pr_number: str
    material: str
    quantity: int
    delivery_date: date
    specifications: Optional[str] = None
    scope_of_work: Optional[str] = None
    technical_specifications: Optional[str] = None
    submission_deadline: Optional[datetime] = None
    payment_terms: Optional[str] = None
    evaluation_criteria: Optional[str] = None
    public_link: Optional[str] = None
    invited_vendors_count: int = 0
    last_sent_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class RFQSendRequest(BaseModel):
    vendor_ids: List[str] = Field(default_factory=list)


class RFQManualCreateRequest(BaseModel):
    pr_id: Optional[str] = None
    pr_number: Optional[str] = None
    material_name: str = Field(..., min_length=2, max_length=255)
    category: Optional[str] = Field(default=None, max_length=120)
    quantity: int = Field(..., ge=1)
    delivery_date: date
    specifications: Optional[str] = Field(default=None, max_length=4000)
    scope_of_work: Optional[str] = Field(default=None, max_length=4000)
    technical_specifications: Optional[str] = Field(default=None, max_length=4000)
    submission_deadline: Optional[datetime] = None
    payment_terms: Optional[str] = Field(default=None, max_length=255)
    evaluation_criteria: Optional[str] = Field(default=None, max_length=4000)


class RFQUpdateRequest(BaseModel):
    material_name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    category: Optional[str] = Field(default=None, max_length=120)
    quantity: Optional[int] = Field(default=None, ge=1)
    delivery_date: Optional[date] = None
    specifications: Optional[str] = Field(default=None, max_length=4000)
    scope_of_work: Optional[str] = Field(default=None, max_length=4000)
    technical_specifications: Optional[str] = Field(default=None, max_length=4000)
    submission_deadline: Optional[datetime] = None
    payment_terms: Optional[str] = Field(default=None, max_length=255)
    evaluation_criteria: Optional[str] = Field(default=None, max_length=4000)


class RFQPublicVendorRegisterRequest(BaseModel):
    vendor_name: str = Field(..., min_length=2, max_length=255)
    email: str = Field(..., min_length=5, max_length=255)
    category: Optional[str] = Field(default=None, max_length=120)
    contact_person: Optional[str] = Field(default=None, max_length=150)
    phone: Optional[str] = Field(default=None, max_length=30)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    country: Optional[str] = Field(default=None, max_length=100)


class RFQDistributionRecord(BaseModel):
    vendor_id: str
    vendor_name: str
    email: Optional[str] = None
    email_status: str
    portal_notification_status: str
    sent_at: Optional[datetime] = None


class RFQDistributionResponse(BaseModel):
    rfq_id: str
    status: str
    delivery_channel: List[str]
    distributions: List[RFQDistributionRecord]


class RFQPublishResponse(BaseModel):
    rfq_id: str
    status: str
    public_link: str
    lifecycle_transition: List[str]
