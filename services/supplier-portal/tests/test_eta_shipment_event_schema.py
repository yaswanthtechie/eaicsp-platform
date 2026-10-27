from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.events import ETAShipmentPredictedEvent


@pytest.fixture
def valid_eta_event():
    return {
        "event_id": str(uuid4()),
        "event_type": "eta.shipment.predicted",
        "event_version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "producer": "eta-prediction",
        "payload": {
            "shipment_id": "SHP-2026-000001",
            "po_number": "PO-2026-000123",
            "eta_days": 5.5,
            "confidence_low": 4.0,
            "confidence_high": 7.0,
            "model_version": "eta_pipeline/3",
            "predicted_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def test_valid_eta_event(valid_eta_event):
    event = ETAShipmentPredictedEvent.model_validate(valid_eta_event)

    assert event.event_type == "eta.shipment.predicted"
    assert event.payload.shipment_id == "SHP-2026-000001"


def test_invalid_confidence_interval(valid_eta_event):
    valid_eta_event["payload"]["confidence_low"] = 8
    valid_eta_event["payload"]["confidence_high"] = 7

    with pytest.raises(ValidationError):
        ETAShipmentPredictedEvent.model_validate(valid_eta_event)


def test_invalid_shipment_id(valid_eta_event):
    valid_eta_event["payload"]["shipment_id"] = "SHP-INVALID"

    with pytest.raises(ValidationError):
        ETAShipmentPredictedEvent.model_validate(valid_eta_event)


def test_wrong_producer(valid_eta_event):
    valid_eta_event["producer"] = "supplier-portal"

    with pytest.raises(ValidationError):
        ETAShipmentPredictedEvent.model_validate(valid_eta_event)


def test_extra_payload_field_rejected(valid_eta_event):
    valid_eta_event["payload"]["unexpected"] = "value"

    with pytest.raises(ValidationError):
        ETAShipmentPredictedEvent.model_validate(valid_eta_event)