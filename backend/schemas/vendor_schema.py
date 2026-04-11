from typing import List, Optional

from pydantic import BaseModel


class VendorCard(BaseModel):
	vendor_id: str
	vendor_name: str
	rating: Optional[float] = None
	performance_pct: Optional[float] = None
	location: str
	email: Optional[str] = None
	category: Optional[str] = None
	past_orders_count: int
	materials_supplied_count: int
	preferred_vendor: bool
	ai_recommended: bool
	ai_score: Optional[float] = None


class VendorCardListResponse(BaseModel):
	total: int
	items: List[VendorCard]


class VendorContactInfo(BaseModel):
	contact_person: Optional[str] = None
	phone: Optional[str] = None
	email: Optional[str] = None


class VendorMasterSection(BaseModel):
	vendor_id: str
	vendor_name: str
	rating: Optional[float] = None
	performance_pct: Optional[float] = None
	location: str
	contact_info: VendorContactInfo
	preferred_vendor: bool
	category: Optional[str] = None
	sub_category: Optional[str] = None


class RiskIndicator(BaseModel):
	level: str
	score: float


class SummaryMetricsSection(BaseModel):
	total_orders: int
	active_contracts: int
	materials_supplied: int
	ai_score: Optional[float] = None
	average_price: Optional[float] = None
	average_delivery_time_days: Optional[float] = None
	risk_indicator: RiskIndicator
	contract_available_for_skip_rfq: bool


class RecentDeal(BaseModel):
	deal_id: str
	po_number: Optional[str] = None
	material_or_service: Optional[str] = None
	quantity: Optional[float] = None
	unit: Optional[str] = None
	unit_price: Optional[float] = None
	total_value: Optional[float] = None
	po_date: Optional[str] = None
	delivery_date: Optional[str] = None
	actual_delivery: Optional[str] = None
	status: Optional[str] = None


class PastDealsSection(BaseModel):
	total_orders: int
	average_price: Optional[float] = None
	delivery_performance_pct: Optional[float] = None
	average_delivery_time_days: Optional[float] = None
	recent_transactions: List[RecentDeal]


class PerformanceScorecardSection(BaseModel):
	on_time_delivery_pct: Optional[float] = None
	quality_score: Optional[float] = None
	defect_rate_pct: Optional[float] = None
	avg_delay_days: Optional[float] = None
	ai_score: Optional[float] = None


class ContractItem(BaseModel):
	contract_id: str
	contract_type: Optional[str] = None
	start_date: Optional[str] = None
	end_date: Optional[str] = None
	agreed_pricing: Optional[str] = None
	contract_value: Optional[float] = None
	status: str
	payment_terms: Optional[str] = None
	auto_renew: bool


class ContractsSection(BaseModel):
	active_contracts: int
	expiring_contracts: int
	expired_contracts: int
	items: List[ContractItem]


class MaterialItem(BaseModel):
	material_code: str
	material_name: Optional[str] = None
	category: Optional[str] = None
	vendor_role: str
	capacity_per_material: Optional[float] = None
	lead_time_days: Optional[float] = None
	contract_available: bool


class MaterialsSection(BaseModel):
	count: int
	items: List[MaterialItem]


class AIInsightsSection(BaseModel):
	strengths: List[str]
	risks: List[str]
	recommendation: str


class VendorProfileResponse(BaseModel):
	vendor_master: VendorMasterSection
	summary_metrics: SummaryMetricsSection
	past_deals: PastDealsSection
	performance_scorecard: PerformanceScorecardSection
	contracts: ContractsSection
	materials: MaterialsSection
	ai_insights: AIInsightsSection
