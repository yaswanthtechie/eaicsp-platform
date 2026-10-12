"""
Unit tests for the Kafka streaming validator, with fake Kafka clients and
the REAL dev rules config (so good/bad records are validated for real).
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from confluent_kafka import KafkaError, KafkaException

import data_validator.streaming_validator as sv_module
from data_validator.postgres_client import PersistenceError
from data_validator.streaming_validator import (
    RETRY_BACKOFF_SECONDS,
    StreamingValidator,
    load_settings,
)
from data_validator.validator import DataValidator

GOOD = {
    "transaction_id": 1, "date": "2024-03-10", "sku_id": "SKU-1000",
    "warehouse_id": "WH-01", "quantity_sold": 5, "unit_price": 20.0,
}
BAD = {
    "transaction_id": 2, "date": "2024-03-11", "sku_id": "BAD-SKU",
    "warehouse_id": "WH-02", "quantity_sold": -5, "unit_price": 10.0,
}

SETTINGS = {
    "bootstrap_servers": "localhost:9092",
    "group_id": "test-group",
    "input_topic": "sales.raw",
    "valid_topic": "sales.valid",
    "dlq_topic": "sales.dlq",
    "config_path": "configs/dev/sales_rules.yaml",
    "persist_every": 100,
    "metrics_port": 8000,
}


class FakeMsg:
    def __init__(self, value, offset=0, error=None):
        self._value = value
        self._offset = offset
        self._error = error

    def value(self):
        return self._value

    def topic(self):
        return "sales.raw"

    def partition(self):
        return 0

    def offset(self):
        return self._offset

    def error(self):
        return self._error


class FakeProducer:
    """Records what was produced; can simulate a failed delivery."""

    def __init__(self, delivery_error=None, raise_on_produce=None):
        self.sent = []
        self.delivery_error = delivery_error
        self.raise_on_produce = raise_on_produce
        self._callback = None

    def produce(self, topic, value, on_delivery=None):
        if self.raise_on_produce:
            raise self.raise_on_produce
        self.sent.append((topic, value))
        self._callback = on_delivery

    def flush(self, timeout=None):
        if self._callback:
            self._callback(self.delivery_error, None)
        return 0


def _msg(record, offset=0):
    payload = record if isinstance(record, str) else json.dumps(record)
    return FakeMsg(payload.encode("utf-8"), offset=offset)


@pytest.fixture
def validator():
    return DataValidator.from_config("configs/dev/sales_rules.yaml")


def _make(validator, producer=None, settings=None, sleep=None):
    consumer = MagicMock()
    sv = StreamingValidator(
        validator,
        consumer,
        producer or FakeProducer(),
        settings or SETTINGS,
        clock=lambda: 100.0,
        sleep=sleep or MagicMock(),
    )
    return sv, consumer


# ------------------------------------------------------------------
# Routing
# ------------------------------------------------------------------

def test_good_record_goes_to_valid_and_is_committed(validator):
    producer = FakeProducer()
    sv, consumer = _make(validator, producer)
    msg = _msg(GOOD)

    assert sv.handle_message(msg) is True

    assert producer.sent[0][0] == "sales.valid"
    consumer.commit.assert_called_once_with(message=msg, asynchronous=False)


def test_bad_record_goes_to_dlq_with_rule_and_reason(validator):
    producer = FakeProducer()
    sv, consumer = _make(validator, producer)

    with patch.object(sv_module, "increment_dlq_count") as dlq_count:
        assert sv.handle_message(_msg(BAD)) is True

    topic, value = producer.sent[0]
    payload = json.loads(value)
    assert topic == "sales.dlq"
    assert payload["original_record"]["transaction_id"] == 2
    assert payload["failed_rules"]
    for rule in payload["failed_rules"]:
        assert payload["reasons"][rule]  # a human-readable reason per rule
    dlq_count.assert_called_once()
    consumer.commit.assert_called_once()


@pytest.mark.parametrize("raw, rule", [
    ("{not json", "json_parse_error"),
    ("[1, 2, 3]", "not_a_json_object"),
])
def test_unusable_messages_go_to_dlq_not_crash(validator, raw, rule):
    producer = FakeProducer()
    sv, consumer = _make(validator, producer)

    assert sv.handle_message(_msg(raw)) is True

    payload = json.loads(producer.sent[0][1])
    assert payload["failed_rules"] == [rule]
    consumer.commit.assert_called_once()


def test_validator_crash_goes_to_dlq_not_crash():
    crashing = MagicMock()
    crashing.rules = []
    crashing.validate_row.side_effect = RuntimeError("engine exploded")
    producer = FakeProducer()
    sv, consumer = _make(crashing, producer)

    assert sv.handle_message(_msg(GOOD)) is True

    payload = json.loads(producer.sent[0][1])
    assert payload["failed_rules"] == ["validator_exception"]
    assert "engine exploded" in payload["reasons"]["validator_exception"]


def test_crashed_rule_is_reported_with_its_reason():
    row_result = MagicMock(
        passed=False,
        errors=[],
        warnings=[],
        skipped_rules=[{"rule": "price_check", "reason": "TypeError: bad"}],
    )
    validator = MagicMock()
    validator.rules = []
    validator.validate_row.return_value = row_result
    producer = FakeProducer()
    sv, _ = _make(validator, producer)

    sv.handle_message(_msg(GOOD))

    payload = json.loads(producer.sent[0][1])
    assert payload["failed_rules"] == ["price_check"]
    assert "Rule could not run" in payload["reasons"]["price_check"]


# ------------------------------------------------------------------
# Delivery: never commit a record whose write was not confirmed
# ------------------------------------------------------------------

def test_failed_delivery_is_not_committed_and_is_retried(validator):
    sleep = MagicMock()
    sv, consumer = _make(
        validator, FakeProducer(delivery_error="broker unavailable"), sleep=sleep
    )
    msg = _msg(GOOD, offset=41)

    assert sv.handle_message(msg) is False

    consumer.commit.assert_not_called()
    seek_target = consumer.seek.call_args[0][0]
    assert (seek_target.topic, seek_target.partition, seek_target.offset) == ("sales.raw", 0, 41)
    sleep.assert_called_once_with(RETRY_BACKOFF_SECONDS)


def test_produce_error_does_not_crash_or_commit(validator):
    sv, consumer = _make(
        validator, FakeProducer(raise_on_produce=BufferError("queue full"))
    )

    assert sv.handle_message(_msg(BAD)) is False
    consumer.commit.assert_not_called()


def test_undelivered_messages_after_flush_are_not_committed(validator):
    producer = FakeProducer()
    producer.flush = lambda timeout=None: 1  # one message still undelivered
    sv, consumer = _make(validator, producer)

    assert sv.handle_message(_msg(GOOD)) is False
    consumer.commit.assert_not_called()


def test_commit_failure_is_logged_not_fatal(validator, caplog):
    sv, consumer = _make(validator)
    consumer.commit.side_effect = KafkaException("coordinator moved")

    assert sv.handle_message(_msg(GOOD)) is True
    assert "Offset commit failed" in caplog.text


# ------------------------------------------------------------------
# Metrics and Postgres persistence from REAL traffic
# ------------------------------------------------------------------

def test_metrics_are_updated_from_real_records(validator):
    sv, _ = _make(validator)

    with patch.object(sv_module, "update_batch_metrics") as update:
        sv.handle_message(_msg(GOOD))
        sv.handle_message(_msg(BAD))

    update.assert_called_with(total_rows=2, affected_rows=1, duration_seconds=0.0)


def test_run_summary_is_persisted_every_n_records(validator):
    settings = dict(SETTINGS, persist_every=2)
    sv, _ = _make(validator, settings=settings)

    with patch.object(sv_module, "persist_validation_result", return_value=7) as persist:
        sv.handle_message(_msg(GOOD))
        persist.assert_not_called()
        sv.handle_message(_msg(BAD))

    persist.assert_called_once()
    kwargs = persist.call_args.kwargs
    assert kwargs["mode"] == "stream"
    assert kwargs["dataset_name"] == "sales.raw"
    assert kwargs["result"].total_rows == 2
    assert kwargs["result"].total_rows_affected == 1
    assert kwargs["result"].evaluated_rules == [r.name for r in validator.rules]
    assert sv.window_processed == 0  # window reset after saving


def test_persistence_failure_is_counted_and_streaming_continues(validator):
    settings = dict(SETTINGS, persist_every=1)
    sv, consumer = _make(validator, settings=settings)

    with patch.object(
        sv_module, "persist_validation_result",
        side_effect=PersistenceError("db down"),
    ), patch.object(sv_module, "record_persist_failure") as failure:
        assert sv.handle_message(_msg(GOOD)) is True

    failure.assert_called_once()
    consumer.commit.assert_called_once()


def test_flush_with_nothing_new_saves_nothing(validator):
    sv, _ = _make(validator)

    with patch.object(sv_module, "persist_validation_result") as persist:
        assert sv.flush_run_summary() is None

    persist.assert_not_called()


# ------------------------------------------------------------------
# Loop, settings and wiring
# ------------------------------------------------------------------

def test_run_loop_skips_errors_handles_messages_and_saves_on_shutdown(validator, caplog):
    sv, consumer = _make(validator)
    eof = MagicMock()
    eof.code.return_value = KafkaError._PARTITION_EOF
    other = MagicMock()
    other.code.return_value = KafkaError._TRANSPORT
    consumer.poll.side_effect = [
        None,
        FakeMsg(b"", error=eof),
        FakeMsg(b"", error=other),
        _msg(GOOD),
        KeyboardInterrupt(),
    ]

    with patch.object(sv_module, "persist_validation_result", return_value=1) as persist:
        sv.run()

    consumer.subscribe.assert_called_once_with(["sales.raw"])
    assert "Consumer error" in caplog.text
    persist.assert_called_once()  # final summary on shutdown
    consumer.close.assert_called_once()


def test_load_settings_reads_environment(monkeypatch):
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
    monkeypatch.setenv("KAFKA_DLQ_TOPIC", "orders.dlq")
    monkeypatch.setenv("STREAM_PERSIST_EVERY", "25")
    monkeypatch.setenv("METRICS_PORT", "9100")

    settings = load_settings()

    assert settings["bootstrap_servers"] == "kafka:29092"
    assert settings["dlq_topic"] == "orders.dlq"
    assert settings["persist_every"] == 25
    assert settings["metrics_port"] == 9100


def test_main_starts_metrics_and_runs_consumer(monkeypatch):
    monkeypatch.setenv("METRICS_PORT", "9100")

    with patch.object(sv_module, "DataValidator") as dv, \
            patch.object(sv_module, "Consumer") as consumer_cls, \
            patch.object(sv_module, "Producer") as producer_cls, \
            patch.object(sv_module, "start_metrics_server") as start_metrics, \
            patch.object(sv_module, "StreamingValidator") as sv_cls:
        sv_module.main()

    start_metrics.assert_called_once_with(9100)
    assert consumer_cls.call_args[0][0]["enable.auto.commit"] is False
    assert producer_cls.call_args[0][0]["enable.idempotence"] is True
    dv.from_config.assert_called_once_with("configs/dev/sales_rules.yaml")
    sv_cls.return_value.run.assert_called_once()