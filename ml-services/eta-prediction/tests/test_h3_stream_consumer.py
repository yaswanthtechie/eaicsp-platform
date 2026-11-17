import json
from unittest.mock import MagicMock, patch
from pathlib import Path

import jsonschema

from src.h2_predict import predict_h2
from src.seed_routes import load_seed_routes
import pytest
from src.eta_publisher import PublishError
from src.paths import SEED_SAMPLES_DIR
from src.stream_consumer import (
    EventDeduplicator,
    build_prediction_event,
    load_settings,
    run,
    validate_event,
)

EXAMPLE_EVENT_PATH = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "events"
    / "examples"
    / "supplierportal.shipment.dispatched.v1.json"
)

VALID_EVENT = json.loads(EXAMPLE_EVENT_PATH.read_text())


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

    result = build_prediction_event(
        VALID_EVENT,
        prediction,
        "eta_seed_routes/1",
    )

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

    if field in (
        "shipment_id",
        "po_number",
        "supplier_id",
        "destination_warehouse",
        "dispatched_at",
    ):
        event["payload"][field] = value
    else:
        event[field] = value

    with pytest.raises(ValueError):
        validate_event(event)


@pytest.mark.parametrize("field", ["origin", "carrier"])
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
        "top_features": [],
    }

    with patch("confluent_kafka.Consumer", return_value=consumer), \
         patch("src.stream_consumer.create_producer", return_value=producer), \
         patch("src.stream_consumer.load_seed_routes", return_value=MagicMock()), \
         patch("src.stream_consumer.load_h2_artifacts"), \
         patch("src.stream_consumer.predict_h2", return_value=prediction), \
         patch("src.stream_consumer.publish_prediction") as publish_mock:

        with pytest.raises(KeyboardInterrupt):
            run({
                "bootstrap_servers": "localhost:9092",
                "group_id": "test-group",
                "input_topic": "supplierportal.shipment.dispatched",
                "output_topic": "eta.shipment.predicted",
                "dlq_topic": "eta.shipment.dispatched.dlq",
                "seed_dir": str(SEED_SAMPLES_DIR),
                "model_version": "eta_seed_routes/1",
            })

    publish_mock.assert_called_once_with(
        producer,
        publish_mock.call_args.args[1],
        "eta.shipment.predicted",
    )

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
         patch("src.stream_consumer.load_seed_routes", return_value=MagicMock()), \
         patch("src.stream_consumer.load_h2_artifacts"), \
         patch("src.stream_consumer.publish_dlq") as dlq_mock:

        with pytest.raises(KeyboardInterrupt):
            run({
                "bootstrap_servers": "localhost:9092",
                "group_id": "test-group",
                "input_topic": "supplierportal.shipment.dispatched",
                "output_topic": "eta.shipment.predicted",
                "dlq_topic": "eta.shipment.dispatched.dlq",
                "seed_dir": str(SEED_SAMPLES_DIR),
                "model_version": "eta_seed_routes/1",
            })

    dlq_mock.assert_called_once()
    consumer.commit.assert_called_once_with(
        message=message,
        asynchronous=False,
    )


def test_run_skips_duplicate_event():
    first_message = MagicMock()
    first_message.value.return_value = json.dumps(VALID_EVENT).encode("utf-8")
    first_message.error.return_value = None
    first_message.topic.return_value = "supplierportal.shipment.dispatched"
    first_message.partition.return_value = 0
    first_message.offset.return_value = 12

    second_message = MagicMock()
    second_message.value.return_value = json.dumps(VALID_EVENT).encode("utf-8")
    second_message.error.return_value = None
    second_message.topic.return_value = "supplierportal.shipment.dispatched"
    second_message.partition.return_value = 0
    second_message.offset.return_value = 13

    consumer = MagicMock()
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
         patch("src.stream_consumer.load_h2_artifacts"), \
         patch("src.stream_consumer.predict_h2", return_value=prediction), \
         patch("src.stream_consumer.publish_prediction") as publish_mock:

        with pytest.raises(KeyboardInterrupt):
            run({
                "bootstrap_servers": "localhost:9092",
                "group_id": "test-group",
                "input_topic": "supplierportal.shipment.dispatched",
                "output_topic": "eta.shipment.predicted",
                "dlq_topic": "eta.shipment.dispatched.dlq",
                "seed_dir": str(SEED_SAMPLES_DIR),
                "model_version": "eta_seed_routes/1",
            })

    assert publish_mock.call_count == 1
    assert consumer.commit.call_count == 2


def test_run_sends_prediction_failure_to_dlq():
    message = MagicMock()
    message.value.return_value = json.dumps(VALID_EVENT).encode("utf-8")
    message.error.return_value = None
    message.topic.return_value = "supplierportal.shipment.dispatched"
    message.partition.return_value = 0
    message.offset.return_value = 14

    consumer = MagicMock()
    consumer.poll.side_effect = [message, KeyboardInterrupt]

    producer = MagicMock()

    with patch("confluent_kafka.Consumer", return_value=consumer), \
         patch("src.stream_consumer.create_producer", return_value=producer), \
         patch("src.stream_consumer.load_seed_routes", return_value=MagicMock()), \
         patch("src.stream_consumer.load_h2_artifacts"), \
         patch(
             "src.stream_consumer.predict_h2",
             side_effect=ValueError("prediction failed"),
         ), \
         patch("src.stream_consumer.publish_dlq") as dlq_mock:

        with pytest.raises(KeyboardInterrupt):
            run({
                "bootstrap_servers": "localhost:9092",
                "group_id": "test-group",
                "input_topic": "supplierportal.shipment.dispatched",
                "output_topic": "eta.shipment.predicted",
                "dlq_topic": "eta.shipment.dispatched.dlq",
                "seed_dir": str(SEED_SAMPLES_DIR),
                "model_version": "eta_seed_routes/1",
            })

    dlq_mock.assert_called_once()
    consumer.commit.assert_called_once_with(
        message=message,
        asynchronous=False,
    )


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
         patch("src.stream_consumer.load_h2_artifacts"), \
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
                    "seed_dir": str(SEED_SAMPLES_DIR),
                    "model_version": "eta_seed_routes/1",
                })

    assert "ETA event latency:" in caplog.text
    assert "processing_ms=" in caplog.text
    assert "end_to_end_ms=" in caplog.text


def test_load_settings_uses_defaults():
    settings = load_settings({})

    assert settings["bootstrap_servers"] == "localhost:9092"
    assert settings["group_id"] == "eta-prediction-v1"
    assert settings["input_topic"] == "supplierportal.shipment.dispatched"
    assert settings["output_topic"] == "eta.shipment.predicted"
    assert settings["dlq_topic"] == "supplierportal.shipment.dispatched.dlq"


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

def test_deduplicator_evicts_oldest():
    deduplicator = EventDeduplicator(max_size=2)

    deduplicator.mark_processed("a")
    deduplicator.mark_processed("b")

    assert deduplicator.is_duplicate("a") is True
    assert deduplicator.is_duplicate("b") is True

    deduplicator.mark_processed("c")

    assert deduplicator.is_duplicate("a") is False
    assert deduplicator.is_duplicate("b") is True
    assert deduplicator.is_duplicate("c") is True

def test_run_does_not_commit_when_publish_fails():
    message = MagicMock()
    message.value.return_value = json.dumps(VALID_EVENT).encode("utf-8")
    message.error.return_value = None
    message.topic.return_value = VALID_EVENT["event_type"]
    message.partition.return_value = 0
    message.offset.return_value = 1

    consumer = MagicMock()
    consumer.poll.side_effect = [message, KeyboardInterrupt]

    settings = {
        "bootstrap_servers": "localhost:9092",
        "group_id": "test-group",
        "input_topic": "supplierportal.shipment.dispatched",
        "output_topic": "eta.shipment.predicted",
        "dlq_topic": "supplierportal.shipment.dispatched.dlq",
        "seed_dir": str(SEED_SAMPLES_DIR),
        "model_version": "eta_seed_routes/1",
    }

    with patch("confluent_kafka.Consumer", return_value=consumer), \
         patch("src.stream_consumer.create_producer"), \
         patch("src.stream_consumer.load_h2_artifacts"), \
         patch("src.stream_consumer.predict_h2", return_value={
             "eta_days": 4.2,
             "confidence_low": 2.0,
             "confidence_high": 6.0,
             "top_features": [],
         }), \
         patch(
             "src.stream_consumer.publish_prediction",
             side_effect=PublishError("down"),
         ):
        with pytest.raises(PublishError, match="down"):
            run(settings)

    consumer.commit.assert_not_called()

def test_run_sends_tombstone_to_dlq():
    message = MagicMock()
    message.value.return_value = None
    message.error.return_value = None
    message.topic.return_value = "supplierportal.shipment.dispatched"
    message.partition.return_value = 0
    message.offset.return_value = 1

    consumer = MagicMock()
    consumer.poll.side_effect = [message, KeyboardInterrupt]

    settings = {
        "bootstrap_servers": "localhost:9092",
        "group_id": "test-group",
        "input_topic": "supplierportal.shipment.dispatched",
        "output_topic": "eta.shipment.predicted",
        "dlq_topic": "supplierportal.shipment.dispatched.dlq",
        "seed_dir": str(SEED_SAMPLES_DIR),
        "model_version": "eta_seed_routes/1",
    }

    with patch("confluent_kafka.Consumer", return_value=consumer), \
         patch("src.stream_consumer.create_producer"), \
         patch("src.stream_consumer.load_h2_artifacts"), \
         patch("src.stream_consumer.publish_dlq") as mock_dlq:
        with pytest.raises(KeyboardInterrupt):
            run(settings)

    mock_dlq.assert_called_once()
    consumer.commit.assert_called_once()

def test_real_route_prediction_matches_output_contract():
    routes = load_seed_routes(SEED_SAMPLES_DIR)
    route = routes.iloc[0]

    event = {
        "event_id": "f3a19d62-7c84-4b1e-9a56-2d7e8c4f0b13",
        "occurred_at": "2026-10-15T06:30:00Z",
        "payload": {
            "shipment_id": "SHP-2026-000077",
            "po_number": "PO-2026-000123",
            "supplier_id": route["supplier_id"],
            "destination_warehouse": route["warehouse_id"],
            "carrier": "BlueDart",
            "dispatched_at": "2026-10-15T06:30:00Z",
        },
    }

    prediction = predict_h2(event["payload"], routes)
    result = build_prediction_event(
        event,
        prediction,
        "eta_seed_routes/1",
    )

    contract_path = (
        Path(__file__).resolve().parents[3]
        / "contracts"
        / "events"
        / "eta.shipment.predicted.v1.json"
    )

    schema = json.loads(contract_path.read_text())
    jsonschema.validate(
        result,
        schema,
        format_checker=jsonschema.FormatChecker(),
    )


def test_unknown_supplier_raises_value_error():
    routes = load_seed_routes(SEED_SAMPLES_DIR)

    with pytest.raises(ValueError, match="Unknown supplier_id"):
        predict_h2(
            {
                "supplier_id": "SUP-99999",
                "destination_warehouse": "WH-BLR-01",
                "carrier": "BlueDart",
                "dispatched_at": "2026-10-15T06:30:00Z",
            },
            routes,
        )
def test_validate_event_rejects_timezone_less_occurred_at():
    event = VALID_EVENT.copy()
    event["occurred_at"] = "2026-10-15T06:30:00"

    with pytest.raises(ValueError, match="timezone is required"):
        validate_event(event)


def test_validate_event_rejects_date_only_occurred_at():
    event = VALID_EVENT.copy()
    event["occurred_at"] = "2026-10-15"

    with pytest.raises(ValueError, match="timezone is required"):
        validate_event(event)


def test_validate_event_rejects_timezone_less_dispatched_at():
    event = VALID_EVENT.copy()
    event["payload"] = event["payload"].copy()
    event["payload"]["dispatched_at"] = "2026-10-15T06:30:00"

    with pytest.raises(ValueError, match="timezone is required"):
        validate_event(event)

def test_run_sends_timezone_less_occurred_at_to_dlq_and_commits():
    event = json.loads(json.dumps(VALID_EVENT))
    event["occurred_at"] = "2026-10-15T06:30:00"

    message = MagicMock()
    message.value.return_value = json.dumps(event).encode("utf-8")
    message.error.return_value = None
    message.topic.return_value = "supplierportal.shipment.dispatched"
    message.partition.return_value = 0
    message.offset.return_value = 15

    consumer = MagicMock()
    consumer.poll.side_effect = [message, KeyboardInterrupt]

    producer = MagicMock()

    settings = {
        "bootstrap_servers": "localhost:9092",
        "group_id": "test-group",
        "input_topic": "supplierportal.shipment.dispatched",
        "output_topic": "eta.shipment.predicted",
        "dlq_topic": "supplierportal.shipment.dispatched.dlq",
        "seed_dir": str(SEED_SAMPLES_DIR),
        "model_version": "eta_seed_routes/1",
    }

    with patch("confluent_kafka.Consumer", return_value=consumer), \
         patch("src.stream_consumer.create_producer", return_value=producer), \
         patch("src.stream_consumer.load_seed_routes", return_value=MagicMock()), \
         patch("src.stream_consumer.load_h2_artifacts"), \
         patch("src.stream_consumer.publish_dlq") as dlq_mock, \
         patch("src.stream_consumer.publish_prediction") as publish_mock:

        with pytest.raises(KeyboardInterrupt):
            run(settings)

    dlq_mock.assert_called_once()
    publish_mock.assert_not_called()
    consumer.commit.assert_called_once_with(
        message=message,
        asynchronous=False,
    )

def test_run_continues_on_non_fatal_kafka_error():
    kafka_error = MagicMock()
    kafka_error.fatal.return_value = False

    error_message = MagicMock()
    error_message.error.return_value = kafka_error

    valid_message = MagicMock()
    valid_message.value.return_value = json.dumps(VALID_EVENT).encode("utf-8")
    valid_message.error.return_value = None
    valid_message.topic.return_value = "supplierportal.shipment.dispatched"
    valid_message.partition.return_value = 0
    valid_message.offset.return_value = 16

    consumer = MagicMock()
    consumer.poll.side_effect = [
        error_message,
        valid_message,
        KeyboardInterrupt,
    ]

    producer = MagicMock()

    prediction = {
        "eta_days": 4.5,
        "confidence_low": 3.0,
        "confidence_high": 6.0,
        "top_features": [],
    }

    settings = {
        "bootstrap_servers": "localhost:9092",
        "group_id": "test-group",
        "input_topic": "supplierportal.shipment.dispatched",
        "output_topic": "eta.shipment.predicted",
        "dlq_topic": "supplierportal.shipment.dispatched.dlq",
        "seed_dir": str(SEED_SAMPLES_DIR),
        "model_version": "eta_seed_routes/1",
    }

    with patch("confluent_kafka.Consumer", return_value=consumer), \
         patch("src.stream_consumer.create_producer", return_value=producer), \
         patch("src.stream_consumer.load_seed_routes", return_value=MagicMock()), \
         patch("src.stream_consumer.load_h2_artifacts"), \
         patch("src.stream_consumer.predict_h2", return_value=prediction), \
         patch("src.stream_consumer.publish_prediction") as publish_mock:

        with pytest.raises(KeyboardInterrupt):
            run(settings)

    publish_mock.assert_called_once()
def test_run_stops_on_fatal_kafka_error():
    kafka_error = MagicMock()
    kafka_error.fatal.return_value = True

    error_message = MagicMock()
    error_message.error.return_value = kafka_error

    consumer = MagicMock()
    consumer.poll.return_value = error_message

    producer = MagicMock()

    settings = {
        "bootstrap_servers": "localhost:9092",
        "group_id": "test-group",
        "input_topic": "supplierportal.shipment.dispatched",
        "output_topic": "eta.shipment.predicted",
        "dlq_topic": "supplierportal.shipment.dispatched.dlq",
        "seed_dir": str(SEED_SAMPLES_DIR),
        "model_version": "eta_seed_routes/1",
    }

    with patch("confluent_kafka.Consumer", return_value=consumer), \
         patch("src.stream_consumer.create_producer", return_value=producer), \
         patch("src.stream_consumer.load_seed_routes", return_value=MagicMock()), \
         patch("src.stream_consumer.load_h2_artifacts"):

        with pytest.raises(Exception):
            run(settings)

ETA_CONTRACT_PATH = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "events"
    / "eta.shipment.predicted.v1.json"
)

ETA_CONTRACT = json.loads(ETA_CONTRACT_PATH.read_text())

PREDICTION = {
    "eta_days": 5.2,
    "confidence_low": 4.1,
    "confidence_high": 7.3,
    "top_features": [],
}

RUN_SETTINGS = {
    "bootstrap_servers": "localhost:9092",
    "group_id": "test-group",
    "input_topic": "supplierportal.shipment.dispatched",
    "output_topic": "eta.shipment.predicted",
    "dlq_topic": "supplierportal.shipment.dispatched.dlq",
    "seed_dir": str(SEED_SAMPLES_DIR),
    "model_version": "eta_seed_routes/1",
}


def _event_with(**payload_fields):
    event = json.loads(json.dumps(VALID_EVENT))
    event["payload"].update(payload_fields)
    return event


def _message_for(event, offset):
    message = MagicMock()
    message.value.return_value = json.dumps(event).encode("utf-8")
    message.error.return_value = None
    message.topic.return_value = "supplierportal.shipment.dispatched"
    message.partition.return_value = 0
    message.offset.return_value = offset
    return message


@pytest.mark.parametrize(
    ("planned_date", "expected_delay"),
    [
        ("2026-10-19", 1),
        ("2026-10-21", -1),
        ("2026-10-20", 0),
    ],
)
def test_prediction_event_delay_fields(planned_date, expected_delay):
    event = _event_with(planned_delivery_date=planned_date)

    result = build_prediction_event(
        event,
        PREDICTION,
        "eta_seed_routes/1",
    )

    assert result["payload"]["planned_delivery_date"] == planned_date
    assert result["payload"]["predicted_delay_days"] == expected_delay

    jsonschema.validate(
        result,
        ETA_CONTRACT,
        format_checker=jsonschema.FormatChecker(),
    )


def test_prediction_event_omits_delay_fields_without_planned_date():
    result = build_prediction_event(
        VALID_EVENT,
        PREDICTION,
        "eta_seed_routes/1",
    )

    assert "planned_delivery_date" not in result["payload"]
    assert "predicted_delay_days" not in result["payload"]

    jsonschema.validate(
        result,
        ETA_CONTRACT,
        format_checker=jsonschema.FormatChecker(),
    )


def test_prediction_event_calculates_delay_using_utc_date():
    event = _event_with(
        dispatched_at="2026-10-15T21:00:00-05:00",
        planned_delivery_date="2026-10-19",
    )

    prediction = {
        **PREDICTION,
        "eta_days": 4.0,
    }

    result = build_prediction_event(
        event,
        prediction,
        "eta_seed_routes/1",
    )

    assert result["payload"]["predicted_delay_days"] == 1


@pytest.mark.parametrize(
    "missing_field",
    [
        "planned_delivery_date",
        "predicted_delay_days",
    ],
)
def test_prediction_event_contract_requires_delay_fields_together(
    missing_field,
):
    result = build_prediction_event(
        _event_with(planned_delivery_date="2026-10-19"),
        PREDICTION,
        "eta_seed_routes/1",
    )

    del result["payload"][missing_field]

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            result,
            ETA_CONTRACT,
            format_checker=jsonschema.FormatChecker(),
        )


@pytest.mark.parametrize(
    "planned_date",
    [
        "2026-15-45",
        "19/10/2026",
        "2026-10-19T00:00:00Z",
        20261019,
        "",
    ],
)
def test_validate_event_rejects_invalid_planned_delivery_date(planned_date):
    event = _event_with(planned_delivery_date=planned_date)

    with pytest.raises(ValueError, match="planned_delivery_date"):
        validate_event(event)


def test_validate_event_accepts_valid_planned_delivery_date():
    event = _event_with(planned_delivery_date="2026-10-19")

    validated = validate_event(event)

    assert validated["payload"]["planned_delivery_date"] == "2026-10-19"


def test_run_sends_invalid_planned_date_to_dlq_and_commits():
    event = _event_with(planned_delivery_date="2026-15-45")
    message = _message_for(event, 30)

    consumer = MagicMock()
    consumer.poll.side_effect = [message, KeyboardInterrupt]

    producer = MagicMock()

    with (
        patch("confluent_kafka.Consumer", return_value=consumer),
        patch("src.stream_consumer.create_producer", return_value=producer),
        patch("src.stream_consumer.load_seed_routes", return_value=MagicMock()),
        patch("src.stream_consumer.load_h2_artifacts"),
        patch("src.stream_consumer.publish_dlq") as dlq_mock,
        patch("src.stream_consumer.publish_prediction") as publish_mock,
    ):
        with pytest.raises(KeyboardInterrupt):
            run(RUN_SETTINGS)

    dlq_mock.assert_called_once()
    publish_mock.assert_not_called()
    consumer.commit.assert_called_once_with(
        message=message,
        asynchronous=False,
    )


def test_run_publishes_prediction_with_valid_planned_date():
    event = _event_with(planned_delivery_date="2026-10-19")
    message = _message_for(event, 31)

    consumer = MagicMock()
    consumer.poll.side_effect = [message, KeyboardInterrupt]

    producer = MagicMock()

    with (
        patch("confluent_kafka.Consumer", return_value=consumer),
        patch("src.stream_consumer.create_producer", return_value=producer),
        patch("src.stream_consumer.load_seed_routes", return_value=MagicMock()),
        patch("src.stream_consumer.load_h2_artifacts"),
        patch("src.stream_consumer.predict_h2", return_value=PREDICTION),
        patch("src.stream_consumer.publish_prediction") as publish_mock,
    ):
        with pytest.raises(KeyboardInterrupt):
            run(RUN_SETTINGS)

    publish_mock.assert_called_once()

    published_event = publish_mock.call_args.args[1]

    assert published_event["payload"]["planned_delivery_date"] == "2026-10-19"
    assert "predicted_delay_days" in published_event["payload"]

    consumer.commit.assert_called_once_with(
        message=message,
        asynchronous=False,
    )
