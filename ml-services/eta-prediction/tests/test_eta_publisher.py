from src.eta_publisher import publish_prediction, publish_dlq
from src.stream_consumer import build_prediction_event
from unittest.mock import MagicMock
import pytest

VALID_EVENT = {
    "event_id": "f3a19d62-7c84-4b1e-9a56-2d7e8c4f0b13",
    "event_type": "supplierportal.shipment.dispatched",
    "event_version": 1,
    "occurred_at": "2026-10-15T06:30:00Z",
    "producer": "supplier-portal",
    "payload": {
        "shipment_id": "SHP-2026-000077",
        "po_number": "PO-2026-000123",
        "supplier_id": "SUP-00045",
        "origin": "Supplier Warehouse, Bengaluru",
        "destination_warehouse": "WH-BLR-01",
        "carrier": "BlueDart",
        "dispatched_at": "2026-10-15T06:30:00Z",
    },
}



def test_publish_prediction_uses_shipment_id_as_kafka_key():
    class FakeFuture:
        def get(self):
            return None

    class FakeProducer:
        def __init__(self):
            self.calls = []

        def send(self, topic, key, value):
            self.calls.append(
                {
                    "topic": topic,
                    "key": key,
                    "value": value,
                }
            )
            return FakeFuture()

    producer = FakeProducer()

    event = build_prediction_event(
        VALID_EVENT,
        {
            "eta_days": 4.5,
            "confidence_low": 3.0,
            "confidence_high": 6.0,
            "top_features": [],
        },
    )

    publish_prediction(producer, event)

    assert len(producer.calls) == 1
    assert producer.calls[0]["topic"] == "eta.shipment.predicted"
    assert producer.calls[0]["key"] == "SHP-2026-000077"
    assert producer.calls[0]["value"] == event

def test_publish_dlq_sends_failed_message_to_dlq():
    class FakeFuture:
        def get(self):
            return None

    class FakeProducer:
        def __init__(self):
            self.calls = []

        def send(self, topic, key, value):
            self.calls.append(
                {
                    "topic": topic,
                    "key": key,
                    "value": value,
                }
            )
            return FakeFuture()

    producer = FakeProducer()

    publish_dlq(
        producer=producer,
        raw_message='{"bad": "event"}',
        error_reason="Missing payload fields",
        topic="supplierportal.shipment.dispatched",
        consumer_group="eta-prediction-v1",
        partition=0,
        offset=42,
    )

    assert len(producer.calls) == 1

    call = producer.calls[0]

    assert call["topic"] == "eta.shipment.dispatched.dlq"
    assert call["key"] == "supplierportal.shipment.dispatched-0-42"
    assert call["value"]["raw_message"] == '{"bad": "event"}'
    assert call["value"]["error"] == "Missing payload fields"
    assert call["value"]["consumer_group"] == "eta-prediction-v1"
    assert call["value"]["topic"] == "supplierportal.shipment.dispatched"
    assert call["value"]["partition"] == 0
    assert call["value"]["offset"] == 42
    assert "failed_at" in call["value"]

def test_publish_prediction_propagates_kafka_failure():
    producer = MagicMock()
    future = MagicMock()
    future.get.side_effect = RuntimeError("Kafka publish failed")
    producer.send.return_value = future

    event = {
        "payload": {
            "shipment_id": "SHP-2026-000077",
        },
        "event_id": "test-event-id",
    }

    with pytest.raises(RuntimeError, match="Kafka publish failed"):
        publish_prediction(producer, event)

    producer.send.assert_called_once()    