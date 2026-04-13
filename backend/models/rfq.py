import uuid
from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Integer, String, Text, UniqueConstraint

from backend.config.constants import DistributionStatus, RFQStatus
from backend.db.base import Base


class RFQ(Base):
    __tablename__ = "rfqs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    rfq_number = Column(String(40), unique=True, index=True, nullable=False)

    pr_id = Column(String(36), index=True, nullable=False)
    pr_number = Column(String(30), index=True, nullable=False)

    material_name = Column(String(255), nullable=False)
    category = Column(String(120), nullable=True)
    quantity = Column(Integer, nullable=False)
    delivery_date = Column(Date, nullable=False)

    specifications = Column(Text, nullable=True)
    scope_of_work = Column(Text, nullable=True)
    technical_specifications = Column(Text, nullable=True)
    submission_deadline = Column(DateTime, nullable=True)
    payment_terms = Column(String(255), nullable=True)
    evaluation_criteria = Column(Text, nullable=True)

    status = Column(String(20), nullable=False, default=RFQStatus.DRAFT.value)
    public_link = Column(String(512), nullable=True)
    pdf_path = Column(String(512), nullable=True)
    invited_vendors_count = Column(Integer, nullable=False, default=0)
    last_sent_at = Column(DateTime, nullable=True)

    published_at = Column(DateTime, nullable=True)
    open_for_bidding_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class RFQDistribution(Base):
    __tablename__ = "rfq_distributions"
    __table_args__ = (UniqueConstraint("rfq_id", "vendor_id", name="uq_rfq_vendor_distribution"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    rfq_id = Column(String(36), index=True, nullable=False)

    vendor_id = Column(String(50), index=True, nullable=False)
    vendor_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)

    email_status = Column(String(20), nullable=False, default=DistributionStatus.PENDING.value)
    portal_notification_status = Column(String(20), nullable=False, default=DistributionStatus.PENDING.value)
    sent_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
