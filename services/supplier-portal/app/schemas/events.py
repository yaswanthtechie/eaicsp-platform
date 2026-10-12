
from enum import Enum
from typing import List

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


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
