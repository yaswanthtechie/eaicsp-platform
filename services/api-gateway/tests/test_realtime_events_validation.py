"""
Tests for Realtime Event Envelope and Payload Validation (R15-M3).

Verifies the six canonical dashboard event types, envelope constraints,
rejection of malformed/invalid/unsupported schemas, and additive field compatibility.
"""

import copy
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.schemas.realtime_events import (
    CANONICAL_EVENT_TYPES,
    validate_realtime_event,
)


# ---------------------------------------------------------------------------
# Golden Fixtures for the 6 Canonical Events
# ---------------------------------------------------------------------------

INVENTORY_STOCK_LOW_SAMPLE = {
    "event_id": str(uuid.uuid4()),
    "event_type": "inventory.stock.low",
    "event_version": 1,
    "occurred_at": "2026-10-15T10:14:22.481203+00:00",
    "producer": "inventory-service",
    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    "payload": {
        "sku_id": "SKU-000123",
        "warehouse_id": "WH-BLR-01",
        "quantity_on_hand": 8,
        "reorder_point": 35,
        "safety_stock": 15,
        "avg_daily_demand": 4.5,
    },
}

IOT_ANOMALY_DETECTED_SAMPLE = {
    "event_id": str(uuid.uuid4()),
    "event_type": "iot.anomaly.detected",
    "event_version": 1,
    "occurred_at": "2026-10-15T10:46:12.418532+00:00",
    "producer": "anomaly-detection-service",
    "trace_id": None,
    "payload": {
        "episode_id": "WH-BLR-01-S1|2026-10-15T10:05:00+00:00",
        "sensor_id": "WH-BLR-01-S1",
        "warehouse_id": "WH-BLR-01",
        "severity": "high",
        "message": "Temperature unusually high at WH-BLR-01: 6 abnormal readings.",
        "window_start": "2026-10-15T10:05:00+00:00",
        "window_end": "2026-10-15T10:30:00+00:00",
        "first_flag_time": "2026-10-15T10:05:00+00:00",
        "confirmed_time": "2026-10-15T10:05:00+00:00",
        "peak_time": "2026-10-15T10:20:00+00:00",
        "peak_score": 0.0825,
        "threshold": -0.0782,
        "n_flagged": 6,
        "severe": True,
        "closed_by": "quiet",
        "top_features": [
            {"feature": "temperature", "contribution": 0.84, "shap_value": 0.07, "direction": "high"},
            {"feature": "power", "contribution": 0.12, "shap_value": 0.01, "direction": "high"},
        ],
        "model_version": "stream-1.0",
    },
}

SUPPLIER_RISK_SCORE_CHANGED_SAMPLE = {
    "event_id": str(uuid.uuid4()),
    "event_type": "supplierrisk.score.changed",
    "event_version": 1,
    "occurred_at": "2026-10-15T10:22:10.118342+00:00",
    "producer": "supplier-risk-service",
    "trace_id": "tr-sr-1234",
    "payload": {
        "supplier": "Apex Industries Pvt Ltd",
        "supplier_id": "SUP-00031",
        "previous_tier": "low",
        "new_tier": "high",
        "risk_score": 78.5,
        "evidence_count": 3,
        "explanation": "Risk tier escalated from low to high following severe regulatory filings.",
        "supporting_articles": [
            {"headline": "Port dock strike delays parts", "date": "2026-10-14", "score": 0.88}
        ],
    },
}

ETA_SHIPMENT_PREDICTED_SAMPLE = {
    "event_id": str(uuid.uuid4()),
    "event_type": "eta.shipment.predicted",
    "event_version": 1,
    "occurred_at": "2026-10-15T06:31:05Z",
    "producer": "eta-prediction",
    "trace_id": None,
    "payload": {
        "shipment_id": "SHP-2026-000077",
        "po_number": "PO-2026-000123",
        "eta_days": 5.2,
        "confidence_low": 4.1,
        "confidence_high": 7.3,
        "model_version": "eta_pipeline/3",
        "predicted_at": "2026-10-15T06:31:04Z",
        "top_features": [{"feature": "distance_km", "shap_value": 1.84}],
    },
}

FORECAST_BATCH_COMPLETED_SAMPLE = {
    "event_id": str(uuid.uuid4()),
    "event_type": "forecast.batch.completed",
    "event_version": 1,
    "occurred_at": "2026-10-15T06:15:30Z",
    "producer": "demand-forecast-service",
    "trace_id": "2d8f99ab114e410b9918c5e003ba7251",
    "payload": {
        "run_id": "BATCH-20261015-01",
        "model_version": "prophet-xgb-r5",
        "granularity": "monthly",
        "sku_count": 500,
        "warehouse_count": 6,
        "horizon": 30,
        "completed_at": "2026-10-15T06:15:28Z",
        "status": "SUCCESS",
        "metrics": {"mape": 0.118, "wape": 0.094},
        "duration_seconds": 142.6,
        "destination_mart": "clickhouse.demand_forecast_history",
        "message": "Monthly demand forecast batch completed.",
    },
}

DATA_PIPELINE_COMPLETED_SAMPLE = {
    "event_id": str(uuid.uuid4()),
    "event_type": "data.pipeline.completed",
    "event_version": 1,
    "occurred_at": "2026-10-15T08:30:15Z",
    "producer": "etl",
    "trace_id": "993a4bc03e12480bb41209e843c01192",
    "payload": {
        "run_id": 1042,
        "status": "SUCCESS",
        "batches_seen": 12,
        "rows_inserted": 12450,
        "rows_updated": 320,
        "rows_rejected": 0,
        "task_states": {
            "dbt_build": "success",
            "clickhouse_load": "success",
        },
        "duration_seconds": 184.2,
        "pipeline_name": "sales_etl_pipeline",
        "message": "Sales ETL pipeline run #1042 completed.",
    },
}

CONTRACT_EXAMPLES = Path(__file__).resolve().parents[3] / "contracts" / "events" / "examples"

# Use the actual producer example from the canonical event contract.
SALES_ANOMALY_DETECTED_SAMPLE = json.loads(
    (CONTRACT_EXAMPLES / "anomaly.sales.detected.v1.json").read_text(encoding="utf-8")
)

SALES_ANOMALY_DETECTED_SAMPLE["payload"]["severity"] = "high"

ALL_SAMPLES = [
    INVENTORY_STOCK_LOW_SAMPLE,
    IOT_ANOMALY_DETECTED_SAMPLE,
    SUPPLIER_RISK_SCORE_CHANGED_SAMPLE,
    ETA_SHIPMENT_PREDICTED_SAMPLE,
    FORECAST_BATCH_COMPLETED_SAMPLE,
    DATA_PIPELINE_COMPLETED_SAMPLE,
    SALES_ANOMALY_DETECTED_SAMPLE,
]


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------


def test_canonical_event_types_count():
    """Ensure exactly the seven canonical dashboard event types are defined."""
    assert len(CANONICAL_EVENT_TYPES) == 7
    expected = {
        "inventory.stock.low",
        "iot.anomaly.detected",
        "supplierrisk.score.changed",
        "eta.shipment.predicted",
        "forecast.batch.completed",
        "data.pipeline.completed",
        "anomaly.sales.detected",
    }
    assert CANONICAL_EVENT_TYPES == expected


@pytest.mark.parametrize("sample", ALL_SAMPLES)
def test_all_seven_canonical_events_validate_successfully(sample):
    """Each canonical event example must pass validation."""
    valid, dedup_key, error = validate_realtime_event(sample)
    assert valid is True
    assert error is None
    assert dedup_key is not None
    assert len(dedup_key) > 0


def test_iot_anomaly_dedup_key_is_episode_id():
    """iot.anomaly.detected must return payload.episode_id as its dedup key."""
    valid, dedup_key, error = validate_realtime_event(IOT_ANOMALY_DETECTED_SAMPLE)
    assert valid is True
    assert dedup_key == IOT_ANOMALY_DETECTED_SAMPLE["payload"]["episode_id"]
    assert dedup_key != IOT_ANOMALY_DETECTED_SAMPLE["event_id"]


@pytest.mark.parametrize("sample", [
    INVENTORY_STOCK_LOW_SAMPLE,
    SUPPLIER_RISK_SCORE_CHANGED_SAMPLE,
    ETA_SHIPMENT_PREDICTED_SAMPLE,
    FORECAST_BATCH_COMPLETED_SAMPLE,
    DATA_PIPELINE_COMPLETED_SAMPLE,
    SALES_ANOMALY_DETECTED_SAMPLE,
])
def test_non_iot_dedup_key_is_event_id(sample):
    """All events other than iot.anomaly.detected deduplicate on envelope event_id."""
    valid, dedup_key, error = validate_realtime_event(sample)
    assert valid is True
    assert dedup_key == sample["event_id"]


@pytest.mark.parametrize("missing_field", [
    "event_id",
    "event_type",
    "event_version",
    "occurred_at",
    "producer",
    "payload",
])
def test_missing_required_envelope_fields_fail(missing_field):
    """Events missing any envelope field must fail validation."""
    event = copy.deepcopy(INVENTORY_STOCK_LOW_SAMPLE)
    del event[missing_field]
    valid, dedup_key, error = validate_realtime_event(event)
    assert valid is False
    assert f"Missing required envelope field(s): {missing_field}" in error


def test_invalid_event_id_format_fails():
    """Non-UUID event_id must fail validation."""
    event = copy.deepcopy(INVENTORY_STOCK_LOW_SAMPLE)
    event["event_id"] = "not-a-valid-uuid"
    valid, dedup_key, error = validate_realtime_event(event)
    assert valid is False
    assert "Invalid event_id" in error


def test_unsupported_event_type_fails():
    """Event types outside the canonical six must fail validation."""
    event = copy.deepcopy(INVENTORY_STOCK_LOW_SAMPLE)
    event["event_type"] = "orders.order.cancelled"
    valid, dedup_key, error = validate_realtime_event(event)
    assert valid is False
    assert "Unsupported event_type" in error


def test_unsupported_event_version_fails():
    """event_version != 1 must fail validation."""
    event = copy.deepcopy(INVENTORY_STOCK_LOW_SAMPLE)
    event["event_version"] = 2
    valid, dedup_key, error = validate_realtime_event(event)
    assert valid is False
    assert "Unsupported event_version '2'" in error


def test_invalid_occurred_at_timestamp_fails():
    """occurred_at not in ISO format must fail validation."""
    event = copy.deepcopy(INVENTORY_STOCK_LOW_SAMPLE)
    event["occurred_at"] = "invalid-date-string"
    valid, dedup_key, error = validate_realtime_event(event)
    assert valid is False
    assert "Invalid occurred_at timestamp" in error


def test_empty_producer_fails():
    """Empty or non-string producer must fail validation."""
    event = copy.deepcopy(INVENTORY_STOCK_LOW_SAMPLE)
    event["producer"] = "   "
    valid, dedup_key, error = validate_realtime_event(event)
    assert valid is False
    assert "Invalid producer" in error


def test_non_dict_event_fails():
    """Non-dict root payload must fail validation."""
    valid, dedup_key, error = validate_realtime_event("a string, not a dict")
    assert valid is False
    assert "must be a JSON object" in error


def test_additive_fields_in_payload_are_allowed():
    """Additive backward-compatible fields in payload must pass validation."""
    event = copy.deepcopy(INVENTORY_STOCK_LOW_SAMPLE)
    event["payload"]["future_additive_field"] = "new-value"
    event["payload"]["another_metric"] = 42
    valid, dedup_key, error = validate_realtime_event(event)
    assert valid is True
    assert error is None


def test_invalid_supplierrisk_tier_fails():
    """supplierrisk.score.changed with invalid tier enum must fail."""
    event = copy.deepcopy(SUPPLIER_RISK_SCORE_CHANGED_SAMPLE)
    event["payload"]["new_tier"] = "catastrophic"
    valid, dedup_key, error = validate_realtime_event(event)
    assert valid is False
    assert "Payload validation error for 'supplierrisk.score.changed'" in error


def test_invalid_forecast_status_fails():
    """forecast.batch.completed with invalid status enum must fail."""
    event = copy.deepcopy(FORECAST_BATCH_COMPLETED_SAMPLE)
    event["payload"]["status"] = "FAILED_TOTALLY"
    valid, dedup_key, error = validate_realtime_event(event)
    assert valid is False
    assert "Payload validation error for 'forecast.batch.completed'" in error


def test_missing_payload_field_fails():
    """Missing required payload fields must fail validation."""
    event = copy.deepcopy(INVENTORY_STOCK_LOW_SAMPLE)
    del event["payload"]["sku_id"]
    valid, dedup_key, error = validate_realtime_event(event)
    assert valid is False
    assert "Field required" in error


@pytest.mark.parametrize(
    "base_sample,field_name,invalid_id",
    [
        (INVENTORY_STOCK_LOW_SAMPLE, "sku_id", "SKU-0001"),
        (INVENTORY_STOCK_LOW_SAMPLE, "warehouse_id", "WH-1"),
        (IOT_ANOMALY_DETECTED_SAMPLE, "warehouse_id", "BLR-01"),
        (SUPPLIER_RISK_SCORE_CHANGED_SAMPLE, "supplier_id", "SUP045"),
        (ETA_SHIPMENT_PREDICTED_SAMPLE, "shipment_id", "SHP-77"),
        (ETA_SHIPMENT_PREDICTED_SAMPLE, "po_number", "PO123"),
    ],
    ids=[
        "invalid_sku_id",
        "invalid_warehouse_id_inventory",
        "invalid_warehouse_id_iot",
        "invalid_supplier_id",
        "invalid_shipment_id",
        "invalid_po_number",
    ],
)
def test_non_canonical_ids_fail(base_sample, field_name, invalid_id):
    """Payloads with non-canonical IDs must fail schema validation."""
    event = copy.deepcopy(base_sample)
    event["payload"][field_name] = invalid_id
    valid, dedup_key, error = validate_realtime_event(event)
    assert valid is False
    assert dedup_key is None
    assert f"Payload validation error for '{event['event_type']}'" in error


@pytest.mark.parametrize(
    "invalid_version",
    [True, 1.0, "1"],
    ids=["bool_true", "float_one", "string_one"],
)
def test_event_version_must_be_integer_one(invalid_version):
    """event_version must be strictly integer 1; True, 1.0, and '1' must be rejected."""
    event = copy.deepcopy(INVENTORY_STOCK_LOW_SAMPLE)
    event["event_version"] = invalid_version
    valid, dedup_key, error = validate_realtime_event(event)
    assert valid is False
    assert dedup_key is None
    assert "Unsupported event_version" in error

    # Ensure integer 1 remains accepted
    event["event_version"] = 1
    valid_ok, _, error_ok = validate_realtime_event(event)
    assert valid_ok is True
    assert error_ok is None


@pytest.mark.parametrize("delay", [4.0, 5, 1.5, 0, -1.0, -3])
def test_eta_predicted_delay_days_validation(delay):
    """ETA prediction payload accepts positive, zero, and negative predicted_delay_days."""
    event = copy.deepcopy(ETA_SHIPMENT_PREDICTED_SAMPLE)
    event["payload"]["predicted_delay_days"] = delay
    valid, dedup_key, error = validate_realtime_event(event)
    assert valid is True
    assert error is None
    assert dedup_key == event["event_id"]


def test_sales_anomaly_contract_example_is_valid():
    """Validate canonical contract example directly and confirm dedup_key == event_id."""
    raw_sample = json.loads(
        (CONTRACT_EXAMPLES / "anomaly.sales.detected.v1.json").read_text(encoding="utf-8")
    )
    valid, dedup_key, error = validate_realtime_event(raw_sample)
    assert valid is True
    assert error is None
    assert dedup_key == raw_sample["event_id"]


@pytest.mark.parametrize("sev", ["low", "medium", "high"])
def test_sales_anomaly_valid_severity(sev):
    """Sales anomaly event accepts lowercase low, medium, and high severity."""
    event = copy.deepcopy(SALES_ANOMALY_DETECTED_SAMPLE)
    event["payload"]["severity"] = sev
    valid, dedup_key, error = validate_realtime_event(event)
    assert valid is True
    assert error is None
    assert dedup_key == event["event_id"]


@pytest.mark.parametrize(
    "invalid_sev",
    ["critical", "extreme", "catastrophic", "", "unknown", "HIGH", "Medium"],
)
def test_sales_anomaly_invalid_severity_fails(invalid_sev):
    """Sales anomaly event rejects invalid severity values."""
    event = copy.deepcopy(SALES_ANOMALY_DETECTED_SAMPLE)
    event["payload"]["severity"] = invalid_sev
    valid, dedup_key, error = validate_realtime_event(event)
    assert valid is False
    assert dedup_key is None
    assert "Payload validation error for 'anomaly.sales.detected'" in error


def test_sales_anomaly_missing_severity_fails():
    """Sales anomaly event rejects payload missing the required severity field."""
    event = copy.deepcopy(SALES_ANOMALY_DETECTED_SAMPLE)
    del event["payload"]["severity"]
    valid, dedup_key, error = validate_realtime_event(event)
    assert valid is False
    assert dedup_key is None
    assert "Payload validation error for 'anomaly.sales.detected'" in error


@pytest.mark.parametrize(
    "missing_field",
    [
        "sku_id",
        "warehouse_id",
        "date",
        "expected_quantity",
        "actual_quantity",
        "score",
    ],
)
def test_sales_anomaly_missing_required_payload_field_fails(missing_field):
    """Sales anomaly event rejects payload missing any required contract field."""
    event = copy.deepcopy(SALES_ANOMALY_DETECTED_SAMPLE)
    del event["payload"][missing_field]
    valid, dedup_key, error = validate_realtime_event(event)
    assert valid is False
    assert dedup_key is None
    assert "Payload validation error for 'anomaly.sales.detected'" in error


@pytest.mark.parametrize(
    "field_name,invalid_val",
    [
        ("sku_id", "ABC"),
        ("sku_id", "PRD-10482"),
        ("warehouse_id", "BLR-01"),
        ("date", "15/10/2026"),
    ],
    ids=[
        "invalid_sku_abc",
        "invalid_sku_prd_prefix",
        "invalid_warehouse_missing_prefix",
        "invalid_date_format",
    ],
)
def test_sales_anomaly_non_canonical_values_fail(field_name, invalid_val):
    """Sales anomaly event rejects non-canonical SKU, warehouse, and date formats."""
    event = copy.deepcopy(SALES_ANOMALY_DETECTED_SAMPLE)
    event["payload"][field_name] = invalid_val
    valid, dedup_key, error = validate_realtime_event(event)
    assert valid is False
    assert dedup_key is None
    assert "Payload validation error for 'anomaly.sales.detected'" in error


@pytest.mark.parametrize("field_name", ["expected_quantity", "actual_quantity"])
def test_sales_anomaly_negative_quantities_fail(field_name):
    """Sales anomaly event rejects negative expected_quantity or actual_quantity."""
    event = copy.deepcopy(SALES_ANOMALY_DETECTED_SAMPLE)
    event["payload"][field_name] = -1.0
    valid, dedup_key, error = validate_realtime_event(event)
    assert valid is False
    assert dedup_key is None
    assert "Payload validation error for 'anomaly.sales.detected'" in error
