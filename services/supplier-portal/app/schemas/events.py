
from enum import Enum
from typing import List

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from datetime import date


# ============================================================
# SUPPLIER COMPLIANCE STATUS
# ============================================================


class SupplierComplianceStatus(str, Enum):
    cleared = "cleared"
    needs_review = "needs_review"
    suspended = "suspended"


# ============================================================
# KAFKA SUPPLIER STATUS CHANGED PAYLOAD
# ============================================================


class SupplierStatusChangedPayload(BaseModel):
    """Payload published by the Compliance Service."""

    supplier_name: str = Field(min_length=1)
    country: str | None = None
    old_status: str = Field(min_length=1)
    new_status: str = Field(min_length=1)
    matched_list: List[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)
    screening_run_id: str = Field(min_length=1)


# ============================================================
# KAFKA STANDARD EVENT ENVELOPE
# ============================================================


class SupplierStatusChangedEvent(BaseModel):
    """Standard envelope for compliance.supplier.status_changed."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_id": "8f6e9c42-7f6c-4b7a-9b6e-123456789abc",
                "event_type": "compliance.supplier.status_changed",
                "event_version": 1,
                "occurred_at": "2026-10-08T09:00:00+00:00",
                "producer": "compliance-service",
                "payload": {
                    "supplier_name": "ABC Supplies",
                    "country": "India",
                    "old_status": "CLEAR",
                    "new_status": "BLOCK",
                    "matched_list": ["OFAC"],
                    "reason": "Matched supplier on OFAC",
                    "screening_run_id": "run-001",
                },
            }
        }
    )

    event_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    event_version: int = Field(gt=0)
    occurred_at: AwareDatetime
    producer: str = Field(min_length=1)
    payload: SupplierStatusChangedPayload


# ============================================================
# SUPPLIER COMPLIANCE AUDIT
# ============================================================


class SupplierComplianceAudit(BaseModel):
    """Audit record for a supplier compliance status change."""

    event_id: str = Field(min_length=1)
    supplier_key: str = Field(min_length=1)
    old_status: SupplierComplianceStatus
    new_status: SupplierComplianceStatus
    matched_list: List[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)
    occurred_at: AwareDatetime
    processed_at: AwareDatetime

# ============================================================
# R15: INVENTORY PURCHASE ORDER APPROVED EVENT
# ============================================================
class ApprovedPOLinePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_number: int = Field(ge=1)
    sku_id: str = Field(pattern=r"^SKU-\d{6}$")
    quantity: int = Field(ge=1)
    unit_cost: float = Field(ge=0)
    expected_cost: float = Field(ge=0)


class ApprovedPOPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    po_id: str = Field(pattern=r"^PO-\d{4}-\d{6}$")
    supplier_id: str = Field(pattern=r"^SUP-\d{5}$")
    warehouse_id: str = Field(pattern=r"^WH-[A-Z]{3}-\d{2}$")
    approval_status: str = Field(pattern=r"^approved$")
    approved_by: str = Field(min_length=1)
    approved_at: AwareDatetime
    total_amount: float = Field(ge=0)
    lines: list[ApprovedPOLinePayload] = Field(min_length=1)

    po_number: str | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    expected_delivery_date: date | None = None


class POApprovedEvent(BaseModel):
    """Event envelope published by Inventory Service."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=36)
    event_type: str = Field(pattern=r"^inventory\.po\.approved$")
    event_version: int = Field(ge=1, le=1)
    occurred_at: AwareDatetime
    producer: str = Field(pattern=r"^inventory-service$")
    trace_id: str | None = None
    payload: ApprovedPOPayload
