from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime, date
from backend.config.constants import PRStatus, AIStatus


# ─── Input Schemas ────────────────────────────────────────────────────────────

class PRCreate(BaseModel):
    item_name: str = Field(..., min_length=2, max_length=255, description="Name of the item to procure")
    category: str = Field(..., min_length=2, max_length=100, description="Procurement category")
    quantity: int = Field(..., ge=1, description="Quantity required (must be >= 1)")
    budget: float = Field(..., gt=0, description="Total allocated budget in INR (must be > 0)")
    description: str = Field(..., min_length=10, max_length=2000, description="Detailed description of the request")
    expected_delivery_date: date = Field(..., description="Expected delivery date (must be a future date)")

    @field_validator("item_name", "category", "description")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()

    @field_validator("expected_delivery_date")
    @classmethod
    def validate_future_delivery_date(cls, v: date) -> date:
        if v <= date.today():
            raise ValueError("expected_delivery_date must be a future date")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "item_name": "Dell Latitude 5540 Laptop",
                "category": "IT Hardware",
                "quantity": 10,
                "budget": 750000.00,
                "expected_delivery_date": "2026-05-20",
                "description": "Laptops for the new engineering team joining in Q2."
            }
        }
    }


class PRUpdate(BaseModel):
    item_name: Optional[str] = Field(None, min_length=2, max_length=255)
    category: Optional[str] = Field(None, min_length=2, max_length=100)
    quantity: Optional[int] = Field(None, ge=1)
    budget: Optional[float] = Field(None, gt=0)
    description: Optional[str] = Field(None, min_length=10, max_length=2000)
    expected_delivery_date: Optional[date] = Field(None, description="Expected delivery date (must be a future date)")
    status: Optional[PRStatus] = None

    @field_validator("item_name", "category", "description", mode="before")
    @classmethod
    def strip_whitespace(cls, v):
        if v is not None:
            return v.strip()
        return v

    @field_validator("expected_delivery_date")
    @classmethod
    def validate_future_delivery_date(cls, v):
        if v is not None and v <= date.today():
            raise ValueError("expected_delivery_date must be a future date")
        return v


class DescriptionRewriteRequest(BaseModel):
    description: str = Field(..., min_length=10, max_length=2000)
    item_name: Optional[str] = Field(None, min_length=2, max_length=255)
    category: Optional[str] = Field(None, min_length=2, max_length=100)
    quantity: Optional[int] = Field(None, ge=1)
    budget: Optional[float] = Field(None, gt=0)
    expected_delivery_date: Optional[date] = None

    @field_validator("description", "item_name", "category", mode="before")
    @classmethod
    def strip_rewrite_fields(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v


class DescriptionRewriteResponse(BaseModel):
    rewritten_description: str
    missing_details: List[str]


# ─── AI Validation Schema ─────────────────────────────────────────────────────

class AIValidationResult(BaseModel):
    improved_description: str
    missing_fields: List[str]
    budget_feedback: str
    status: AIStatus


# ─── Response Schemas ─────────────────────────────────────────────────────────

class PRResponse(BaseModel):
    id: str
    pr_number: str
    item_name: str
    category: str
    quantity: int
    budget: float
    budget_per_unit: Optional[float] = None
    expected_delivery_date: date
    description: str
    status: PRStatus
    pdf_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PRListResponse(BaseModel):
    total: int
    items: List[PRResponse]
