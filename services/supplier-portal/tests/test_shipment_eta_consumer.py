
import json
from datetime import date, datetime, timezone

import pytest

from app.models.shipment import Shipment
from app.models.shipment_eta_event import ShipmentETAEvent
from app.services.shipment_eta_consumer import ShipmentETAConsumer
from unittest.mock import Mock, call, patch


SHIPMENT_ID = "SHP-2026-000001"
PO_NUMBER = "PO-2026-000001"
SUPPLIER_ID = "SUP-00001"


class FakeKafkaMessage:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def value(self):
        return self._payload

class FakeKafkaRecord(FakeKafkaMessage):
    def topic(self):
        return "eta.shipment.predicted"

    def partition(self):
        return 0

    def offset(self):
        return 10

    def key(self):
        return b"SHP-2026-000001"

def create_shipment(db):
    shipment = Shipment(
        shipment_id=SHIPMENT_ID,
        po_number=PO_NUMBER,
        supplier_id=SUPPLIER_ID,
        shipment_date=date(2026, 10, 26),
        expected_delivery_date=date(2026, 10, 30),
        carrier="Test Carrier",
        tracking_number="TRACK-001",
        origin="Hyderabad",
        destination_warehouse="WH-BLR-01",
        items=[],
        status="dispatched",
        created_by="supplier@company.com",
        dispatched_at=datetime(
            2026, 10, 26, 10, 0, tzinfo=timezone.utc
        ),
    )
    db.add(shipment)
    db.commit()


def create_eta_event():
    return {
        "event_id": "123e4567-e89b-42d3-a456-426614174000",
        "event_type": "eta.shipment.predicted",
        "event_version": 1,
        "occurred_at": "2026-10-26T10:30:00Z",
        "producer": "eta-prediction",
        "payload": {
            "shipment_id": SHIPMENT_ID,
            "po_number": PO_NUMBER,
            "eta_days": 4.5,
            "confidence_low": 3.0,
            "confidence_high": 6.0,
            "model_version": "eta-model-v1",
            "predicted_at": "2026-10-26T10:30:00Z",
            "top_features": [
                {
                    "feature": "distance_km",
                    "shap_value": 0.35,
                }
            ],
        },
    }


def create_consumer():
    return ShipmentETAConsumer.__new__(ShipmentETAConsumer)


def process_event(consumer, event):
    return consumer.process_message(FakeKafkaMessage(event))


def test_eta_prediction_is_saved_to_shipment(po_db):
    db = po_db()
    try:
        create_shipment(db)

        assert process_event(
            create_consumer(),
            create_eta_event(),
        ) is True

        db.expire_all()
        shipment = db.get(Shipment, SHIPMENT_ID)

        assert shipment.eta_days == 4.5
        assert shipment.confidence_low == 3.0
        assert shipment.confidence_high == 6.0
        assert shipment.model_version == "eta-model-v1"
        assert shipment.predicted_at is not None
        assert shipment.top_features == [
            {
                "feature": "distance_km",
                "shap_value": 0.35,
            }
        ]
    finally:
        db.close()


def test_duplicate_eta_event_is_not_saved_twice(po_db):
    db = po_db()
    try:
        create_shipment(db)
        consumer = create_consumer()
        event = create_eta_event()

        assert process_event(consumer, event) is True
        assert process_event(consumer, event) is True

        count = (
            db.query(ShipmentETAEvent)
            .filter_by(event_id=event["event_id"])
            .count()
        )
        assert count == 1

    finally:
        db.close()


def test_newer_eta_prediction_updates_existing_prediction(po_db):
    db = po_db()
    try:
        create_shipment(db)
        consumer = create_consumer()

        first_event = create_eta_event()
        assert process_event(consumer, first_event) is True

        newer_event = create_eta_event()
        newer_event["event_id"] = (
            "223e4567-e89b-42d3-a456-426614174000"
        )
        newer_event["occurred_at"] = "2026-10-26T11:30:00Z"
        newer_event["payload"]["eta_days"] = 2.5
        newer_event["payload"]["confidence_low"] = 2.0
        newer_event["payload"]["confidence_high"] = 3.0
        newer_event["payload"]["model_version"] = "eta-model-v2"
        newer_event["payload"]["predicted_at"] = (
            "2026-10-26T11:30:00Z"
        )

        assert process_event(consumer, newer_event) is True

        db.expire_all()
        shipment = db.get(Shipment, SHIPMENT_ID)

        assert shipment.eta_days == 2.5
        assert shipment.confidence_low == 2.0
        assert shipment.confidence_high == 3.0
        assert shipment.model_version == "eta-model-v2"
        assert shipment.predicted_at is not None

    finally:
        db.close()


def test_older_eta_prediction_does_not_overwrite_newer_prediction(po_db):
    db = po_db()
    try:
        create_shipment(db)
        consumer = create_consumer()

        newer_event = create_eta_event()
        newer_event["event_id"] = (
            "323e4567-e89b-42d3-a456-426614174000"
        )
        newer_event["payload"]["eta_days"] = 2.5
        newer_event["payload"]["predicted_at"] = (
            "2026-10-26T11:30:00Z"
        )

        assert process_event(consumer, newer_event) is True

        older_event = create_eta_event()
        older_event["event_id"] = (
            "423e4567-e89b-42d3-a456-426614174000"
        )
        older_event["payload"]["eta_days"] = 5.5
        older_event["payload"]["predicted_at"] = (
            "2026-10-26T10:30:00Z"
        )

        assert process_event(consumer, older_event) is True

        db.expire_all()
        shipment = db.get(Shipment, SHIPMENT_ID)

        assert shipment.eta_days == 2.5

        event_count = db.query(ShipmentETAEvent).count()
        assert event_count == 2

    finally:
        db.close()


def test_unknown_shipment_is_rejected(po_db):
    db = po_db()
    try:
        event = create_eta_event()
        event["payload"]["shipment_id"] = "SHP-2026-999999"

        with pytest.raises(ValueError):
            process_event(create_consumer(), event)

        assert db.query(ShipmentETAEvent).count() == 0

    finally:
        db.close()


def test_po_number_mismatch_is_rejected(po_db):
    db = po_db()
    try:
        create_shipment(db)

        event = create_eta_event()
        event["payload"]["po_number"] = "PO-2026-999999"

        with pytest.raises(ValueError):
            process_event(create_consumer(), event)

        assert db.query(ShipmentETAEvent).count() == 0

    finally:
        db.close()


def test_invalid_eta_event_schema_is_rejected(po_db):
    db = po_db()
    try:
        create_shipment(db)

        event = create_eta_event()
        event["producer"] = "wrong-producer"

        with pytest.raises(ValueError):
            process_event(create_consumer(), event)

        assert db.query(ShipmentETAEvent).count() == 0

    finally:
        db.close()


def test_invalid_confidence_interval_is_rejected(po_db):
    db = po_db()
    try:
        create_shipment(db)

        event = create_eta_event()
        event["payload"]["confidence_low"] = 8.0
        event["payload"]["confidence_high"] = 3.0

        with pytest.raises(ValueError):
            process_event(create_consumer(), event)

        assert db.query(ShipmentETAEvent).count() == 0

    finally:
        db.close()


def test_invalid_top_features_are_rejected(po_db):
    db = po_db()
    try:
        create_shipment(db)

        event = create_eta_event()
        event["payload"]["top_features"] = [
            {
                "feature": "distance_km",
                "shap_value": 0.35,
                "unexpected_field": "not-allowed",
            }
        ]

        with pytest.raises(ValueError):
            process_event(create_consumer(), event)

        assert db.query(ShipmentETAEvent).count() == 0

    finally:
        db.close()


def test_processing_retries_before_success():
    consumer = create_consumer()
    consumer.running = True
    consumer.max_retries = 3
    consumer.retry_backoff = 0
    consumer.consumer = Mock()

    message = FakeKafkaRecord({})

    with patch.object(
        consumer,
        "process_message",
        side_effect=[ValueError("temporary failure"), True],
    ) as process_mock, patch.object(
        consumer,
        "_commit_message",
    ) as commit_mock, patch(
        "app.services.shipment_eta_consumer.time.sleep",
    ) as sleep_mock:

        consumer._process_with_retry(message)

    assert process_mock.call_count == 2
    assert sleep_mock.call_count == 1
    commit_mock.assert_called_once_with(message)


def test_processing_failure_publishes_to_dlq_and_commits():
    consumer = create_consumer()
    consumer.running = True
    consumer.max_retries = 2
    consumer.retry_backoff = 0
    consumer.consumer = Mock()

    message = FakeKafkaRecord({})

    with patch.object(
        consumer,
        "process_message",
        side_effect=ValueError("invalid event"),
    ) as process_mock, patch.object(
        consumer,
        "_publish_to_dlq",
        return_value=True,
    ) as dlq_mock, patch.object(
        consumer,
        "_commit_message",
    ) as commit_mock, patch(
        "app.services.shipment_eta_consumer.time.sleep",
    ):

        consumer._process_with_retry(message)

    assert process_mock.call_count == 2
    dlq_mock.assert_called_once_with(
        message,
        "Maximum retries exceeded",
    )
    commit_mock.assert_called_once_with(message)


def test_dlq_failure_does_not_commit_offset():
    consumer = create_consumer()
    consumer.running = True
    consumer.max_retries = 2
    consumer.retry_backoff = 0
    consumer.consumer = Mock()

    message = FakeKafkaRecord({})

    with patch.object(
        consumer,
        "process_message",
        side_effect=ValueError("invalid event"),
    ), patch.object(
        consumer,
        "_publish_to_dlq",
        return_value=False,
    ), patch.object(
        consumer,
        "_commit_message",
    ) as commit_mock, patch(
        "app.services.shipment_eta_consumer.time.sleep",
    ):

        with pytest.raises(
            RuntimeError,
            match="Could not publish ETA event to DLQ",
        ):
            consumer._process_with_retry(message)

    commit_mock.assert_not_called()


def test_dlq_publish_returns_true_when_delivery_succeeds():
    consumer = create_consumer()
    consumer.dlq_topic = "eta.shipment.predicted.dlq"
    consumer.producer = Mock()

    def successful_produce(
        topic,
        key,
        value,
        on_delivery,
    ):
        on_delivery(None, Mock())

    consumer.producer.produce.side_effect = successful_produce
    consumer.producer.flush.return_value = 0

    message = FakeKafkaRecord({"sample": "event"})

    result = consumer._publish_to_dlq(
        message,
        "Maximum retries exceeded",
    )

    assert result is True
    consumer.producer.produce.assert_called_once()
    consumer.producer.flush.assert_called_once_with(timeout=10)


def test_dlq_publish_returns_false_when_delivery_fails():
    consumer = create_consumer()
    consumer.dlq_topic = "eta.shipment.predicted.dlq"
    consumer.producer = Mock()

    def failed_produce(
        topic,
        key,
        value,
        on_delivery,
    ):
        on_delivery(RuntimeError("broker unavailable"), None)

    consumer.producer.produce.side_effect = failed_produce
    consumer.producer.flush.return_value = 0

    message = FakeKafkaRecord({"sample": "event"})

    result = consumer._publish_to_dlq(
        message,
        "Maximum retries exceeded",
    )

    assert result is False

