from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from backend.config.constants import PRStatus, AIStatus


# ─── Input Schemas ────────────────────────────────────────────────────────────

class PRCreate(BaseModel):
    item_name: str = Field(..., min_length=2, max_length=255, description="Name of the item to procure")
    category: str = Field(..., min_length=2, max_length=100, description="Procurement category")
    quantity: int = Field(..., ge=1, description="Quantity required (must be >= 1)")
    budget: float = Field(..., gt=0, description="Allocated budget in USD (must be > 0)")
    description: str = Field(..., min_length=10, max_length=2000, description="Detailed description of the request")

    @field_validator("item_name", "category", "description")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()

    model_config = {
        "json_schema_extra": {
            "example": {
                "item_name": "Dell Latitude 5540 Laptop",
                "category": "IT Hardware",
                "quantity": 10,
                "budget": 15000.00,
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
    status: Optional[PRStatus] = None

    @field_validator("item_name", "category", "description", mode="before")
    @classmethod
    def strip_whitespace(cls, v):
        if v is not None:
            return v.strip()
        return v


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
    description: str
    improved_description: Optional[str] = None
    missing_fields: Optional[List[str]] = None
    budget_feedback: Optional[str] = None
    ai_status: AIStatus
    status: PRStatus
    pdf_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PRListResponse(BaseModel):
    total: int
    items: List[PRResponse]
