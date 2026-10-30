"""
Event envelope and payload validation schemas for Realtime WebSocket (R15-M3).

Defines the contract validation for the six canonical dashboard event types:
1. inventory.stock.low
2. iot.anomaly.detected
3. supplierrisk.score.changed
4. eta.shipment.predicted
5. forecast.batch.completed
6. data.pipeline.completed
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


SKU_ID_PATTERN = r"^SKU-\d{6}$"
WAREHOUSE_ID_PATTERN = r"^WH-[A-Z]{3}-\d{2}$"
SUPPLIER_ID_PATTERN = r"^SUP-\d{5}$"
SHIPMENT_ID_PATTERN = r"^SHP-\d{4}-\d{6}$"
PO_NUMBER_PATTERN = r"^PO-\d{4}-\d{6}$"


CANONICAL_EVENT_TYPES: Set[str] = {
    "inventory.stock.low",
    "iot.anomaly.detected",
    "supplierrisk.score.changed",
    "eta.shipment.predicted",
    "forecast.batch.completed",
    "data.pipeline.completed",
}


# ---------------------------------------------------------------------------
# Payload Schemas (Forward-compatible: extra="ignore")
# ---------------------------------------------------------------------------


class InventoryStockLowPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sku_id: str = Field(..., pattern=SKU_ID_PATTERN)
    warehouse_id: str = Field(..., pattern=WAREHOUSE_ID_PATTERN)
    quantity_on_hand: int
    reorder_point: int
    safety_stock: int
    avg_daily_demand: float
    message: Optional[str] = None


class IotAnomalyDetectedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    episode_id: str = Field(..., min_length=1)
    sensor_id: str = Field(..., min_length=1)
    warehouse_id: str = Field(..., pattern=WAREHOUSE_ID_PATTERN)
    severity: str
    message: str = Field(..., min_length=1, max_length=300)
    window_start: str
    window_end: str
    first_flag_time: str
    confirmed_time: str
    peak_time: str
    peak_score: float
    threshold: float
    n_flagged: int = Field(..., ge=1)
    severe: bool
    closed_by: str
    top_features: List[Dict[str, Any]]
    model_version: str

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in {"low", "medium", "high", "critical"}:
            raise ValueError(f"Invalid severity '{v}', must be one of low, medium, high, critical")
        return clean


class SupplierRiskScoreChangedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    supplier: str
    supplier_id: str = Field(..., pattern=SUPPLIER_ID_PATTERN)
    previous_tier: str
    new_tier: str
    risk_score: float = Field(..., ge=0.0, le=100.0)
    evidence_count: int
    explanation: str
    supporting_articles: Optional[List[Dict[str, Any]]] = None

    @field_validator("previous_tier", "new_tier")
    @classmethod
    def validate_tier(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in {"low", "medium", "high"}:
            raise ValueError(f"Invalid tier '{v}', must be low, medium, or high")
        return clean


class EtaShipmentPredictedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    shipment_id: str = Field(..., pattern=SHIPMENT_ID_PATTERN)
    po_number: str = Field(..., pattern=PO_NUMBER_PATTERN)
    eta_days: float = Field(..., ge=0.0)
    confidence_low: float
    confidence_high: float
    model_version: str
    predicted_at: str
    top_features: Optional[List[Dict[str, Any]]] = None


class ForecastBatchCompletedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    run_id: str
    model_version: str
    granularity: str
    sku_count: int
    warehouse_count: int
    horizon: int
    completed_at: str
    status: str
    metrics: Optional[Dict[str, Any]] = None
    duration_seconds: Optional[float] = None
    destination_mart: Optional[str] = None
    message: Optional[str] = None

    @field_validator("granularity")
    @classmethod
    def validate_granularity(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in {"monthly", "daily"}:
            raise ValueError(f"Invalid granularity '{v}', must be monthly or daily")
        return clean

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        clean = v.strip().upper()
        if clean not in {"SUCCESS", "PARTIAL"}:
            raise ValueError(f"Invalid status '{v}', must be SUCCESS or PARTIAL")
        return clean


class DataPipelineCompletedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    run_id: Union[int, str]
    status: str
    batches_seen: int
    rows_inserted: int
    rows_updated: int
    rows_rejected: int
    task_states: Dict[str, Any]
    duration_seconds: Optional[float] = None
    pipeline_name: Optional[str] = None
    message: Optional[str] = None


PAYLOAD_VALIDATORS: Dict[str, type[BaseModel]] = {
    "inventory.stock.low": InventoryStockLowPayload,
    "iot.anomaly.detected": IotAnomalyDetectedPayload,
    "supplierrisk.score.changed": SupplierRiskScoreChangedPayload,
    "eta.shipment.predicted": EtaShipmentPredictedPayload,
    "forecast.batch.completed": ForecastBatchCompletedPayload,
    "data.pipeline.completed": DataPipelineCompletedPayload,
}


# ---------------------------------------------------------------------------
# Envelope Validation
# ---------------------------------------------------------------------------


def is_valid_uuid(val: str) -> bool:
    """Validate that val is a valid UUID string (v4 or standard format)."""
    try:
        uuid_obj = uuid.UUID(str(val))
        return str(uuid_obj).lower() == str(val).lower()
    except (ValueError, AttributeError, TypeError):
        return False


def is_valid_iso_timestamp(val: str) -> bool:
    """Validate ISO-8601 timestamp string with Z or UTC offset."""
    if not isinstance(val, str) or not val.strip():
        return False
    # Standard format parse check
    try:
        clean = val.replace("Z", "+00:00")
        datetime.fromisoformat(clean)
        return True
    except (ValueError, TypeError):
        return False


def validate_realtime_event(data: Any) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate an incoming Kafka message against the M1 envelope and event contract.

    Returns:
        (is_valid, dedup_key, error_reason)
        - If valid: (True, dedup_key, None)
        - If invalid: (False, None, error_reason)
    """
    if not isinstance(data, dict):
        return False, None, f"Event must be a JSON object, got {type(data).__name__}"

    # 1. Check required envelope fields
    required_fields = ["event_id", "event_type", "event_version", "occurred_at", "producer", "payload"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        return False, None, f"Missing required envelope field(s): {', '.join(missing)}"

    # 2. Validate event_id (UUID v4)
    event_id = data.get("event_id")
    if not is_valid_uuid(event_id):
        return False, None, f"Invalid event_id '{event_id}'; must be a valid UUID"

    # 3. Validate event_type
    event_type = data.get("event_type")
    if event_type not in CANONICAL_EVENT_TYPES:
        return False, None, f"Unsupported event_type '{event_type}'. Must be one of: {sorted(CANONICAL_EVENT_TYPES)}"

    # 4. Validate event_version (Major version 1 only)
    event_version = data.get("event_version")
    if type(event_version) is not int or event_version != 1:
        return False, None, f"Unsupported event_version '{event_version}'. Only major version 1 is supported."

    # 5. Validate occurred_at timestamp
    occurred_at = data.get("occurred_at")
    if not is_valid_iso_timestamp(occurred_at):
        return False, None, f"Invalid occurred_at timestamp '{occurred_at}'. Must be ISO-8601 format."

    # 6. Validate producer
    producer = data.get("producer")
    if not isinstance(producer, str) or not producer.strip():
        return False, None, f"Invalid producer '{producer}'. Must be a non-empty string."

    # 7. Validate payload exists and is a dictionary
    payload = data.get("payload")
    if not isinstance(payload, dict):
        return False, None, f"Payload must be a dictionary, got {type(payload).__name__}"

    # 8. Validate payload schema according to event_type
    validator_cls = PAYLOAD_VALIDATORS.get(event_type)
    if validator_cls:
        try:
            validator_cls.model_validate(payload)
        except ValidationError as exc:
            # Format validation errors clearly
            errors = [f"{'.'.join(str(l) for l in err['loc'])}: {err['msg']}" for err in exc.errors()]
            return False, None, f"Payload validation error for '{event_type}': {'; '.join(errors)}"

    # 9. Derive deduplication key
    # For iot.anomaly.detected, deduplicate on payload.episode_id (replay can generate new event_id)
    # For all other events, deduplicate on envelope event_id
    if event_type == "iot.anomaly.detected":
        episode_id = payload.get("episode_id")
        if not episode_id:
            return False, None, "Missing payload.episode_id for iot.anomaly.detected"
        dedup_key = str(episode_id)
    else:
        dedup_key = str(event_id)

    return True, dedup_key, None
