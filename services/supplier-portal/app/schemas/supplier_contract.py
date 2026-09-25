from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


# ============================================================
# CONTRACT STATUS
# ============================================================

class ContractStatus(str, Enum):
    draft = "draft"
    active = "active"
    renewed = "renewed"
    expired = "expired"


# ============================================================
# CONTRACT CREATE REQUEST
# ============================================================

class SupplierContractCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "supplier_id": "SUP001",
                "contract_number": "SC-2026-001",
                "title": "Laptop Supply Agreement",
                "description": "Annual laptop supply agreement",
                "start_date": "2026-04-01",
                "end_date": "2027-03-31",
                "payment_terms": "Net 30",
                "delivery_terms": "7 days",
                "pricing_terms": "Fixed",
                "minimum_order_value": 500000,
                "renewal_notice_days": 30,
                "auto_renew": False
            }
        }
    )

    supplier_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9_-]+$"
    )

    contract_number: str = Field(
        ...,
        min_length=1,
        max_length=100
    )

    title: str = Field(
        ...,
        min_length=2,
        max_length=200
    )

    description: str | None = Field(
        default=None,
        max_length=2000
    )

    start_date: date

    end_date: date

    payment_terms: str = Field(
        ...,
        min_length=2,
        max_length=500
    )

    delivery_terms: str = Field(
        ...,
        min_length=2,
        max_length=500
    )

    pricing_terms: str = Field(
        ...,
        min_length=2,
        max_length=500
    )

    minimum_order_value: float | None = Field(
        default=None,
        ge=0
    )

    renewal_notice_days: int = Field(
        default=30,
        ge=1,
        le=365
    )

    auto_renew: bool = False


# ============================================================
# CONTRACT UPDATE REQUEST
# ============================================================

class SupplierContractUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Updated Laptop Supply Agreement",
                "description": "Updated annual supply agreement",
                "end_date": "2027-06-30",
                "payment_terms": "Net 45",
                "delivery_terms": "10 days",
                "pricing_terms": "Fixed",
                "minimum_order_value": 600000,
                "renewal_notice_days": 45,
                "auto_renew": True
            }
        }
    )

    title: str | None = Field(
        default=None,
        min_length=2,
        max_length=200
    )

    description: str | None = Field(
        default=None,
        max_length=2000
    )

    end_date: date | None = None

    payment_terms: str | None = Field(
        default=None,
        min_length=2,
        max_length=500
    )

    delivery_terms: str | None = Field(
        default=None,
        min_length=2,
        max_length=500
    )

    pricing_terms: str | None = Field(
        default=None,
        min_length=2,
        max_length=500
    )

    minimum_order_value: float | None = Field(
        default=None,
        ge=0
    )

    renewal_notice_days: int | None = Field(
        default=None,
        ge=1,
        le=365
    )

    auto_renew: bool | None = None


# ============================================================
# CONTRACT RENEWAL REQUEST
# ============================================================

class SupplierContractRenewalRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "new_start_date": "2027-04-01",
                "new_end_date": "2028-03-31",
                "reason": "Annual supplier agreement renewed"
            }
        }
    )

    new_start_date: date

    new_end_date: date

    reason: str | None = Field(
        default=None,
        max_length=1000
    )


# ============================================================
# CONTRACT RESPONSE
# ============================================================

class SupplierContractResponse(BaseModel):
    contract_id: str
    supplier_id: str
    contract_number: str
    title: str
    description: str | None
    start_date: date
    end_date: date
    payment_terms: str
    delivery_terms: str
    pricing_terms: str
    minimum_order_value: float | None
    renewal_notice_days: int
    auto_renew: bool
    status: ContractStatus
    expiring_soon: bool
    days_until_expiry: int
    created_at: datetime
    updated_at: datetime
    created_by: str


# ============================================================
# CONTRACT RENEWAL RESPONSE
# ============================================================

class SupplierContractRenewalResponse(BaseModel):
    contract_id: str
    supplier_id: str
    status: ContractStatus
    previous_end_date: date
    new_start_date: date
    new_end_date: date
    renewed_at: datetime
    renewed_by: str
    reason: str | None


# ============================================================
# CONTRACT HISTORY
# ============================================================

class SupplierContractHistory(BaseModel):
    history_id: str
    contract_id: str
    supplier_id: str
    from_status: ContractStatus | None
    to_status: ContractStatus
    actor_id: str
    actor_name: str
    role: str
    reason: str | None
    timestamp: datetime


# ============================================================
# CONTRACT EXPIRY RESPONSE
# ============================================================

class SupplierContractExpiryResponse(BaseModel):
    contract_id: str
    supplier_id: str
    contract_number: str
    title: str
    end_date: date
    renewal_notice_days: int
    days_until_expiry: int
    expiring_soon: bool
    status: ContractStatus