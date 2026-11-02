import json
import pytest
from unittest.mock import MagicMock, patch

from src.stream_consumer import (
    EventDeduplicator,
    build_prediction_event,
    load_settings,
    run,
    validate_event,
)

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


def test_validate_event_accepts_valid_dispatched_event():
    event = validate_event(VALID_EVENT)

    assert event == VALID_EVENT


def test_validate_event_rejects_missing_payload_field():
    event = json.loads(json.dumps(VALID_EVENT))
    del event["payload"]["shipment_id"]

    with pytest.raises(ValueError, match="Missing payload fields"):
        validate_event(event)


def test_build_prediction_event_matches_h3_output():
    prediction = {
        "eta_days": 4.5,
        "confidence_low": 3.0,
        "confidence_high": 6.0,
        "top_features": [
            {"feature": "distance_km", "shap_value": 1.2},
        ],
    }

    result = build_prediction_event(VALID_EVENT, prediction)

    assert result["event_type"] == "eta.shipment.predicted"
    assert result["event_version"] == 1
    assert result["producer"] == "eta-prediction"
    assert result["payload"]["shipment_id"] == "SHP-2026-000077"
    assert result["payload"]["po_number"] == "PO-2026-000123"
    assert result["payload"]["eta_days"] == 4.5
    assert result["payload"]["confidence_low"] == 3.0
    assert result["payload"]["confidence_high"] == 6.0
    assert result["payload"]["model_version"] == "eta_seed_routes/1"


def test_event_deduplicator_detects_duplicate_event_id():
    deduplicator = EventDeduplicator()

    event_id = VALID_EVENT["event_id"]

    assert deduplicator.is_duplicate(event_id) is False

    deduplicator.mark_processed(event_id)

    assert deduplicator.is_duplicate(event_id) is True

def test_validate_event_rejects_wrong_event_type():
    event = json.loads(json.dumps(VALID_EVENT))
    event["event_type"] = "wrong.event.type"

    with pytest.raises(ValueError, match="Unexpected event_type"):
        validate_event(event)


def test_validate_event_rejects_wrong_producer():
    event = json.loads(json.dumps(VALID_EVENT))
    event["producer"] = "wrong-producer"

    with pytest.raises(ValueError, match="Unexpected producer"):
        validate_event(event)

@pytest.mark.parametrize(
    "field,value",
    [
        ("event_id", "invalid-event-id"),
        ("shipment_id", "BAD-SHIPMENT"),
        ("po_number", "BAD-PO"),
        ("supplier_id", "BAD-SUPPLIER"),
        ("destination_warehouse", "BAD-WAREHOUSE"),
        ("dispatched_at", "not-a-datetime"),
        ("occurred_at", "not-a-datetime"),
    ],
)
def test_validate_event_rejects_invalid_field_formats(field, value):
    event = json.loads(json.dumps(VALID_EVENT))

    if field in ("shipment_id", "po_number", "supplier_id", "destination_warehouse", "dispatched_at"):
        event["payload"][field] = value
    else:
        event[field] = value

    with pytest.raises(ValueError):
        validate_event(event)


@pytest.mark.parametrize(
    "field",
    [
        "origin",
        "carrier",
    ],
)
def test_validate_event_rejects_empty_required_text_fields(field):
    event = json.loads(json.dumps(VALID_EVENT))
    event["payload"][field] = ""

    with pytest.raises(ValueError):
        validate_event(event)


def test_validate_event_rejects_non_object_event():
    with pytest.raises(ValueError, match="JSON object"):
        validate_event([])


def test_validate_event_rejects_non_object_payload():
    event = json.loads(json.dumps(VALID_EVENT))
    event["payload"] = []

    with pytest.raises(ValueError, match="payload"):
        validate_event(event)

def test_run_processes_valid_event_and_publishes_prediction():
    message = MagicMock()
    message.value.return_value = json.dumps(VALID_EVENT).encode("utf-8")
    message.error.return_value = None
    message.topic.return_value = "supplierportal.shipment.dispatched"
    message.partition.return_value = 0
    message.offset.return_value = 10

    consumer = MagicMock()
    consumer.poll.side_effect = [message, KeyboardInterrupt]
    
    producer = MagicMock()

    prediction = {
        "eta_days": 4.5,
        "confidence_low": 3.0,
        "confidence_high": 6.0,
        "top_features": [
            {"feature": "distance_km", "shap_value": 0.8},
        ],
    }

    with patch("confluent_kafka.Consumer", return_value=consumer), \
         patch("src.stream_consumer.create_producer", return_value=producer), \
         patch("src.stream_consumer.load_seed_routes", return_value=MagicMock()), \
         patch("src.stream_consumer.predict_h2", return_value=prediction), \
         patch("src.stream_consumer.publish_prediction") as publish_mock:

        with pytest.raises(KeyboardInterrupt):
            run({
                "bootstrap_servers": "localhost:9092",
                "group_id": "test-group",
                "input_topic": "supplierportal.shipment.dispatched",
                "output_topic": "eta.shipment.predicted",
                "dlq_topic": "eta.shipment.dispatched.dlq",
            })

    publish_mock.assert_called_once()
    consumer.commit.assert_called_once_with(
        message=message,
        asynchronous=False,
    )


def test_run_sends_invalid_event_to_dlq():
    invalid_event = json.loads(json.dumps(VALID_EVENT))
    invalid_event["event_type"] = "wrong.event"

    message = MagicMock()
    message.value.return_value = json.dumps(invalid_event).encode("utf-8")
    message.error.return_value = None
    message.topic.return_value = "supplierportal.shipment.dispatched"
    message.partition.return_value = 0
    message.offset.return_value = 11

    consumer = MagicMock()
    consumer.poll.side_effect = [message, KeyboardInterrupt]

    producer = MagicMock()

    with patch("confluent_kafka.Consumer", return_value=consumer), \
         patch("src.stream_consumer.create_producer", return_value=producer), \
         patch("src.stream_consumer.publish_dlq") as dlq_mock:

        with pytest.raises(KeyboardInterrupt):
            run({
                "bootstrap_servers": "localhost:9092",
                "group_id": "test-group",
                "input_topic": "supplierportal.shipment.dispatched",
                "output_topic": "eta.shipment.predicted",
                "dlq_topic": "eta.shipment.dispatched.dlq",
            })

    dlq_mock.assert_called_once()
    consumer.commit.assert_called_once_with(
        message=message,
        asynchronous=False,
    )


def test_run_skips_duplicate_event():
    message = MagicMock()
    message.value.return_value = json.dumps(VALID_EVENT).encode("utf-8")
    message.error.return_value = None

    consumer = MagicMock()

    first_message = message
    second_message = MagicMock()
    second_message.value.return_value = json.dumps(VALID_EVENT).encode("utf-8")
    second_message.error.return_value = None

    consumer.poll.side_effect = [
        first_message,
        second_message,
        KeyboardInterrupt,
    ]

    producer = MagicMock()

    prediction = {
        "eta_days": 4.5,
        "confidence_low": 3.0,
        "confidence_high": 6.0,
        "top_features": [],
    }

    with patch("confluent_kafka.Consumer", return_value=consumer), \
         patch("src.stream_consumer.create_producer", return_value=producer), \
         patch("src.stream_consumer.load_seed_routes", return_value=MagicMock()), \
         patch("src.stream_consumer.predict_h2", return_value=prediction), \
         patch("src.stream_consumer.publish_prediction") as publish_mock:

        with pytest.raises(KeyboardInterrupt):
            run({
                "bootstrap_servers": "localhost:9092",
                "group_id": "test-group",
                "input_topic": "supplierportal.shipment.dispatched",
                "output_topic": "eta.shipment.predicted",
                "dlq_topic": "eta.shipment.dispatched.dlq",
            })

    assert publish_mock.call_count == 1
    assert consumer.commit.call_count == 2


def test_run_does_not_mark_event_processed_when_prediction_fails():
    message = MagicMock()
    message.value.return_value = json.dumps(VALID_EVENT).encode("utf-8")
    message.error.return_value = None

    consumer = MagicMock()
    consumer.poll.side_effect = [message, KeyboardInterrupt]

    producer = MagicMock()

    with patch("confluent_kafka.Consumer", return_value=consumer), \
         patch("src.stream_consumer.create_producer", return_value=producer), \
         patch(
             "src.stream_consumer.load_seed_routes",
             return_value=MagicMock(),
         ), \
         patch(
             "src.stream_consumer.predict_h2",
             side_effect=ValueError("prediction failed"),
         ), \
         patch("src.stream_consumer.publish_prediction"):

        with pytest.raises(ValueError, match="prediction failed"):
            run({
                "bootstrap_servers": "localhost:9092",
                "group_id": "test-group",
                "input_topic": "supplierportal.shipment.dispatched",
                "output_topic": "eta.shipment.predicted",
                "dlq_topic": "eta.shipment.dispatched.dlq",
            })

    consumer.commit.assert_not_called()

def test_run_logs_eta_event_latency(caplog):
    message = MagicMock()
    message.value.return_value = json.dumps(VALID_EVENT).encode("utf-8")
    message.error.return_value = None
    message.topic.return_value = "supplierportal.shipment.dispatched"
    message.partition.return_value = 0
    message.offset.return_value = 20

    consumer = MagicMock()
    consumer.poll.side_effect = [message, KeyboardInterrupt]

    prediction = {
        "eta_days": 4.5,
        "confidence_low": 3.0,
        "confidence_high": 6.0,
        "top_features": [],
    }

    with patch("confluent_kafka.Consumer", return_value=consumer), \
         patch("src.stream_consumer.create_producer"), \
         patch("src.stream_consumer.load_seed_routes", return_value=MagicMock()), \
         patch("src.stream_consumer.predict_h2", return_value=prediction), \
         patch("src.stream_consumer.publish_prediction"):

        with caplog.at_level("INFO"):
            with pytest.raises(KeyboardInterrupt):
                run({
                    "bootstrap_servers": "localhost:9092",
                    "group_id": "test-group",
                    "input_topic": "supplierportal.shipment.dispatched",
                    "output_topic": "eta.shipment.predicted",
                    "dlq_topic": "eta.shipment.dispatched.dlq",
                })

    assert "ETA event latency:" in caplog.text
    assert "latency_ms=" in caplog.text
def test_load_settings_uses_defaults():
    settings = load_settings({})

    assert settings["bootstrap_servers"] == "localhost:9092"
    assert settings["group_id"] == "eta-prediction-v1"
    assert settings["input_topic"] == "supplierportal.shipment.dispatched"
    assert settings["output_topic"] == "eta.shipment.predicted"
    assert settings["dlq_topic"] == "eta.shipment.dispatched.dlq"


def test_load_settings_reads_environment_values():
    settings = load_settings({
        "KAFKA_BOOTSTRAP_SERVERS": "kafka:9092",
        "KAFKA_GROUP_ID": "eta-test-group",
        "KAFKA_INPUT_TOPIC": "input.test",
        "KAFKA_OUTPUT_TOPIC": "output.test",
        "KAFKA_DLQ_TOPIC": "dlq.test",
    })

    assert settings["bootstrap_servers"] == "kafka:9092"
    assert settings["group_id"] == "eta-test-group"
    assert settings["input_topic"] == "input.test"
    assert settings["output_topic"] == "output.test"
    assert settings["dlq_topic"] == "dlq.test"        