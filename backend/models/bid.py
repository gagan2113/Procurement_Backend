import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON

from backend.config.constants import BidStatus
from backend.db.base import Base


class Bid(Base):
	__tablename__ = "bids"
	__table_args__ = (UniqueConstraint("rfq_id", "vendor_id", name="uq_rfq_vendor_bid"),)

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
	rfq_id = Column(String(36), index=True, nullable=False)

	vendor_id = Column(String(50), index=True, nullable=False)
	vendor_name = Column(String(255), nullable=False)

	quoted_price = Column(Float, nullable=False)
	currency = Column(String(10), nullable=False, default="INR")
	quoted_delivery_days = Column(Integer, nullable=False)
	technical_compliance_pct = Column(Float, nullable=False)
	quality_commitment_score = Column(Float, nullable=False)
	warranty_months = Column(Integer, nullable=False, default=0)
	payment_terms_days = Column(Integer, nullable=True)
	notes = Column(Text, nullable=True)

	status = Column(String(20), nullable=False, default=BidStatus.SUBMITTED.value)

	normalized_price = Column(Float, nullable=True)
	normalized_delivery = Column(Float, nullable=True)
	normalized_quality = Column(Float, nullable=True)
	normalization_meta = Column(SQLiteJSON, nullable=True)

	created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
	updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class BidEvaluation(Base):
	__tablename__ = "bid_evaluations"
	__table_args__ = (UniqueConstraint("rfq_id", "bid_id", name="uq_rfq_bid_evaluation"),)

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
	rfq_id = Column(String(36), index=True, nullable=False)
	bid_id = Column(String(36), index=True, nullable=False)

	vendor_id = Column(String(50), index=True, nullable=False)
	vendor_name = Column(String(255), nullable=False)

	price_score = Column(Float, nullable=False)
	delivery_score = Column(Float, nullable=False)
	quality_score = Column(Float, nullable=False)
	risk_score = Column(Float, nullable=False)
	final_score = Column(Float, nullable=False)
	rank = Column(Integer, nullable=False)

	is_selected = Column(Boolean, nullable=False, default=False)
	strengths = Column(SQLiteJSON, nullable=True)
	risks = Column(SQLiteJSON, nullable=True)
	recommendation = Column(String(20), nullable=False, default="Consider")

	created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
	updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
