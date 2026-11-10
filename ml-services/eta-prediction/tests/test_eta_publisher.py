from unittest.mock import MagicMock

import pytest

from src.eta_publisher import PublishError, publish_dlq, publish_prediction
from src.stream_consumer import build_prediction_event


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
    class FakeProducer:
        def __init__(self):
            self.calls = []

        def produce(self, topic, key, value, on_delivery):
            self.calls.append(
                {
                    "topic": topic,
                    "key": key,
                    "value": value,
                    "on_delivery": on_delivery,
                }
            )

            on_delivery(None, None)

        def flush(self, timeout):
            return 0

    producer = FakeProducer()

    event = build_prediction_event(
        VALID_EVENT,
        {
            "eta_days": 4.5,
            "confidence_low": 3.0,
            "confidence_high": 6.0,
            "top_features": [],
        },
        "eta_seed_routes/1",
    )

    publish_prediction(
        producer,
        event,
        "eta.shipment.predicted",
    )

    assert len(producer.calls) == 1

    call = producer.calls[0]

    assert call["topic"] == "eta.shipment.predicted"
    assert call["key"] == b"SHP-2026-000077"
    assert call["value"].decode("utf-8")
    assert call["value"].decode("utf-8").find("SHP-2026-000077") != -1


def test_publish_dlq_sends_failed_message_to_dlq():
    class FakeProducer:
        def __init__(self):
            self.calls = []

        def produce(self, topic, key, value, on_delivery):
            self.calls.append(
                {
                    "topic": topic,
                    "key": key,
                    "value": value,
                    "on_delivery": on_delivery,
                }
            )

            on_delivery(None, None)

        def flush(self, timeout):
            return 0

    producer = FakeProducer()

    publish_dlq(
        producer=producer,
        dlq_topic="supplierportal.shipment.dispatched.dlq",
        raw_message='{"bad": "event"}',
        error_reason="Missing payload fields",
        topic="supplierportal.shipment.dispatched",
        consumer_group="eta-prediction-v1",
        partition=0,
        offset=42,
    )

    assert len(producer.calls) == 1

    call = producer.calls[0]

    assert call["topic"] == "supplierportal.shipment.dispatched.dlq"
    assert call["key"] == b"supplierportal.shipment.dispatched-0-42"

    value = call["value"].decode("utf-8")

    assert '\\"bad\\": \\"event\\"' in value
    assert "Missing payload fields" in value
    assert "eta-prediction-v1" in value
    assert "supplierportal.shipment.dispatched" in value
    assert '"partition": 0' in value
    assert '"offset": 42' in value


def test_publish_prediction_raises_publish_error_on_kafka_failure():
    producer = MagicMock()

    def fail_delivery(topic, key, value, on_delivery=None, **kwargs):
        on_delivery(RuntimeError("Kafka publish failed"), None)

    producer.produce.side_effect = fail_delivery
    producer.flush.return_value = 0

    event = {
        "payload": {
            "shipment_id": "SHP-2026-000077",
        },
        "event_id": "test-event-id",
    }

    with pytest.raises(
        PublishError,
        match="Publish to eta.shipment.predicted failed",
    ):
        publish_prediction(
            producer,
            event,
            "eta.shipment.predicted",
        )

    producer.produce.assert_called_once()