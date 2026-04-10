import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Date, Text
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from backend.db.base import Base
from backend.config.constants import PRStatus, AIStatus


class PurchaseRequest(Base):
    __tablename__ = "purchase_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    pr_number = Column(String(30), unique=True, index=True, nullable=False)

    # Form fields
    item_name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)
    quantity = Column(Integer, nullable=False)
    budget = Column(Float, nullable=False)
    expected_delivery_date = Column(Date, nullable=False)
    description = Column(Text, nullable=False)

    # AI-enhanced fields
    improved_description = Column(Text, nullable=True)
    missing_fields = Column(SQLiteJSON, nullable=True, default=list)
    budget_feedback = Column(Text, nullable=True)
    ai_status = Column(String(20), nullable=False, default=AIStatus.PENDING.value)

    # PR lifecycle status
    status = Column(String(20), nullable=False, default=PRStatus.PENDING.value)

    # PDF
    pdf_path = Column(String(512), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<PurchaseRequest {self.pr_number} | {self.item_name} | {self.status}>"
