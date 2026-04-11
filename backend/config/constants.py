from enum import Enum


class PRStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    APPROVED = "approved"
    REJECTED = "rejected"
    CLOSED = "closed"


class AIStatus(str, Enum):
    VALID = "valid"
    NEEDS_REVIEW = "needs_review"
    PENDING = "pending"


class RFQStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    OPEN = "open"
    CLOSED = "closed"


class DistributionStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class BidStatus(str, Enum):
    SUBMITTED = "submitted"
    EVALUATED = "evaluated"
    SELECTED = "selected"


class ProcurementCategory(str, Enum):
    IT_HARDWARE = "IT Hardware"
    IT_SOFTWARE = "IT Software"
    OFFICE_SUPPLIES = "Office Supplies"
    FURNITURE = "Furniture"
    MACHINERY = "Machinery"
    SERVICES = "Services"
    RAW_MATERIALS = "Raw Materials"
    UTILITIES = "Utilities"
    MAINTENANCE = "Maintenance"
    OTHER = "Other"


# Budget thresholds for validation feedback
BUDGET_THRESHOLDS = {
    "IT Hardware": {"min": 500, "max": 500_000},
    "IT Software": {"min": 100, "max": 200_000},
    "Office Supplies": {"min": 10, "max": 10_000},
    "Furniture": {"min": 200, "max": 50_000},
    "Machinery": {"min": 1_000, "max": 2_000_000},
    "Services": {"min": 500, "max": 1_000_000},
    "Raw Materials": {"min": 100, "max": 500_000},
    "Utilities": {"min": 50, "max": 100_000},
    "Maintenance": {"min": 100, "max": 200_000},
    "Other": {"min": 50, "max": 500_000},
}

PR_NUMBER_PREFIX = "PR"
