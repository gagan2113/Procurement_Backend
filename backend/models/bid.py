import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON

from backend.config.constants import BidStatus
from backend.db.base import Base


class Bid(Base):
	# Persist vendor submissions in quotations table as the source of truth.
	__tablename__ = "quotations"
	__table_args__ = (UniqueConstraint("rfq_id", "vendor_id", name="uq_rfq_vendor_quotation"),)

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
	rfq_id = Column(String(36), index=True, nullable=False)

	vendor_id = Column(String(50), index=True, nullable=False)
	vendor_name = Column(String(255), nullable=False)

	price = Column(Float, nullable=False)
	currency = Column(String(10), nullable=False, default="INR")
	lead_time_days = Column(Integer, nullable=False)
	delivery_schedule = Column(Text, nullable=False)
	delivery_terms = Column(Text, nullable=False)
	payment_terms = Column(Text, nullable=False)
	validity_days = Column(Integer, nullable=False)
	specification_compliance = Column(Float, nullable=False)
	alternative_product = Column(Text, nullable=True)

	quotation_pdf_path = Column(String(512), nullable=True)
	technical_sheet_path = Column(String(512), nullable=True)
	compliance_documents_path = Column(String(512), nullable=True)
	certifications_path = Column(String(512), nullable=True)

	document_status = Column(String(20), nullable=False, default="pending")
	extracted_price = Column(Float, nullable=True)
	extracted_delivery_terms = Column(Text, nullable=True)
	extracted_conditions = Column(Text, nullable=True)
	extracted_compliance_details = Column(Text, nullable=True)
	document_summary = Column(Text, nullable=True)
	document_compliance_score = Column(Float, nullable=True)

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
	reliability_score = Column(Float, nullable=True)
	capability_score = Column(Float, nullable=True)
	document_compliance_score = Column(Float, nullable=True)
	final_score = Column(Float, nullable=False)
	rank = Column(Integer, nullable=False)

	is_selected = Column(Boolean, nullable=False, default=False)
	manual_override = Column(Boolean, nullable=False, default=False)
	score_breakdown = Column(SQLiteJSON, nullable=True)
	strengths = Column(SQLiteJSON, nullable=True)
	risks = Column(SQLiteJSON, nullable=True)
	recommendation = Column(String(20), nullable=False, default="Consider")

	created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
	updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
