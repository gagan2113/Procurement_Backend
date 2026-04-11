from sqlalchemy import Boolean, Column, Date, Float, Integer, String

from backend.db.base import Base


class Vendor(Base):
	__tablename__ = "vendors"

	vendor_id = Column(String(50), primary_key=True, index=True)
	vendor_name = Column(String(255), nullable=False)
	category = Column(String(120), nullable=True)
	sub_category = Column(String(120), nullable=True)
	gstin = Column(String(50), nullable=True)
	pan = Column(String(50), nullable=True)
	city = Column(String(100), nullable=True)
	state = Column(String(100), nullable=True)
	country = Column(String(100), nullable=True)
	contact_person = Column(String(150), nullable=True)
	phone = Column(String(30), nullable=True)
	email = Column(String(255), nullable=True)
	contract_exists = Column(Boolean, nullable=False, default=False)
	contract_id = Column(String(50), nullable=True)
	contract_valid_until = Column(Date, nullable=True)
	sap_vendor_code = Column(String(50), nullable=True)
	payment_terms_days = Column(Integer, nullable=True)
	currency = Column(String(10), nullable=True)


class PurchaseHistory(Base):
	__tablename__ = "purchase_history"

	deal_id = Column(String(50), primary_key=True, index=True)
	vendor_id = Column(String(50), index=True, nullable=False)
	vendor_name = Column(String(255), nullable=True)
	po_number = Column(String(50), nullable=True)
	category = Column(String(120), nullable=True)
	material_or_service = Column(String(255), nullable=True)
	quantity = Column(Float, nullable=True)
	unit = Column(String(40), nullable=True)
	unit_price = Column(Float, nullable=True)
	total_value = Column(Float, nullable=True)
	po_date = Column(Date, nullable=True)
	delivery_date = Column(Date, nullable=True)
	actual_delivery = Column(Date, nullable=True)
	status = Column(String(40), nullable=True)


class VendorPerformance(Base):
	__tablename__ = "vendor_performance"

	vendor_id = Column(String(50), primary_key=True, index=True)
	vendor_name = Column(String(255), nullable=True)
	category = Column(String(120), nullable=True)
	on_time_delivery_pct = Column(Float, nullable=True)
	quality_score = Column(Float, nullable=True)
	price_competitiveness = Column(Float, nullable=True)
	defect_rate_pct = Column(Float, nullable=True)
	response_time_hours = Column(Float, nullable=True)
	compliance_score = Column(Float, nullable=True)
	total_orders = Column(Integer, nullable=True)
	completed_orders = Column(Integer, nullable=True)
	disputes_raised = Column(Integer, nullable=True)
	avg_delay_days = Column(Float, nullable=True)
	risk_level = Column(String(30), nullable=True)
	ai_score = Column(Float, nullable=True)


class Contract(Base):
	__tablename__ = "contracts"

	contract_id = Column(String(50), primary_key=True, index=True)
	vendor_id = Column(String(50), index=True, nullable=False)
	vendor_name = Column(String(255), nullable=True)
	category = Column(String(120), nullable=True)
	contract_type = Column(String(120), nullable=True)
	start_date = Column(Date, nullable=True)
	end_date = Column(Date, nullable=True)
	contract_value = Column(Float, nullable=True)
	negotiated_rate = Column(String(120), nullable=True)
	sla_terms = Column(String(500), nullable=True)
	payment_terms = Column(String(120), nullable=True)
	auto_renew = Column(Boolean, nullable=False, default=False)
	status = Column(String(40), nullable=True)


class MaterialVendorMap(Base):
	__tablename__ = "material_vendor_map"

	material_code = Column(String(50), primary_key=True, index=True)
	material_description = Column(String(255), nullable=True)
	category = Column(String(120), nullable=True)
	primary_vendor_id = Column(String(50), index=True, nullable=True)
	primary_vendor = Column(String(255), nullable=True)
	secondary_vendor_id = Column(String(50), index=True, nullable=True)
	secondary_vendor = Column(String(255), nullable=True)
	contract_available = Column(Boolean, nullable=False, default=False)
	preferred_vendor_id = Column(String(50), index=True, nullable=True)
