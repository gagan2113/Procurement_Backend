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
    created_at: datetime
    updated_at: datetime


class RFQSendRequest(BaseModel):
    vendor_ids: List[str] = Field(default_factory=list, min_length=1)


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
