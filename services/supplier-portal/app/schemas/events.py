from datetime import datetime
from enum import Enum
from typing import List

from pydantic import BaseModel, ConfigDict, Field


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
    """
    Payload received from the Compliance Service when a
    supplier compliance status changes.
    """

    supplier_id: str = Field(
        min_length=1
    )

    old_status: str = Field(
        min_length=1
    )

    new_status: str = Field(
        min_length=1
    )

    matched_list: List[str] = Field(
        default_factory=list
    )

    reason: str = Field(
        min_length=1
    )


# ============================================================
# KAFKA STANDARD EVENT ENVELOPE
# ============================================================


class SupplierStatusChangedEvent(BaseModel):
    """
    Standard Kafka event envelope for
    compliance.supplier.status_changed.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_id": "8f6e9c42-7f6c-4b7a-9b6e-123456789abc",
                "event_type": "compliance.supplier.status_changed",
                "event_version": 1,
                "occurred_at": "2026-10-08T09:00:00+00:00",
                "producer": "compliance",
                "payload": {
                    "supplier_id": "SUP001",
                    "old_status": "CLEAR",
                    "new_status": "BLOCK",
                    "matched_list": [
                        "OFAC"
                    ],
                    "reason": "Matched supplier on OFAC",
                },
            }
        }
    )

    event_id: str = Field(
        min_length=1
    )

    event_type: str = Field(
        min_length=1
    )

    event_version: int = Field(
        gt=0
    )

    occurred_at: datetime

    producer: str = Field(
        min_length=1
    )

    payload: SupplierStatusChangedPayload


# ============================================================
# SUPPLIER COMPLIANCE AUDIT
# ============================================================


class SupplierComplianceAudit(BaseModel):
    """
    Audit record for every accepted supplier compliance
    status change.
    """

    event_id: str = Field(
        min_length=1
    )

    supplier_id: str = Field(
        min_length=1
    )

    old_status: SupplierComplianceStatus

    new_status: SupplierComplianceStatus

    matched_list: List[str] = Field(
        default_factory=list
    )

    reason: str = Field(
        min_length=1
    )

    occurred_at: datetime

    processed_at: datetime