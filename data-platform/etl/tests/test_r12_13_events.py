"""M3 - Kafka pipeline events. Docker-free: SQLite outbox + fake Kafka producer."""
import json
import re
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

import kafka_events as ke


class FakeFuture:
    def __init__(self, exc=None):
        self.exc = exc

    def get(self, timeout=None):
        if self.exc:
            raise self.exc


class FakeProducer:
    def __init__(self, fail_send=False):
        self.sent = []
        self.fail_send = fail_send
        self.closed = False

    def send(self, topic, key=None, value=None):
        if self.fail_send:
            return FakeFuture(RuntimeError("broker not available"))
        self.sent.append({"topic": topic, "key": key, "value": value})
        return FakeFuture()

    def flush(self, timeout=None):
        pass

    def close(self, timeout=None):
        self.closed = True


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    monkeypatch.setattr(ke, "get_engine", lambda: engine)
    return engine


def rows(db):
    with db.connect() as c:
        return c.execute(text(
            "SELECT event_id,status,attempts,last_error,event_type,payload,occurred_at "
            "FROM etl_event_outbox ORDER BY created_at, event_id")).mappings().all()


def kafka_down(monkeypatch):
    def boom():
        raise ConnectionError("NoBrokersAvailable")
    monkeypatch.setattr(ke, "_producer", boom)


# ---- envelope contract ------------------------------------------------------

def test_envelope_matches_the_standard_contract():
    env = ke.build_envelope("data.pipeline.completed", {"run_id": 7})
    assert set(env) == {"event_id", "event_type", "event_version",
                        "occurred_at", "producer", "payload"}
    assert uuid.UUID(env["event_id"]).version == 4
    assert env["event_type"] == "data.pipeline.completed"
    assert env["event_version"] == 1
    assert env["producer"] == "etl"
    assert env["payload"] == {"run_id": 7}
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?Z", env["occurred_at"])


def test_envelope_converts_non_utc_time_to_utc():
    from datetime import timedelta, timezone as tz
    ist = datetime(2026, 9, 29, 15, 45, tzinfo=tz(timedelta(hours=5, minutes=30)))
    assert ke.build_envelope("x", {}, occurred_at=ist)["occurred_at"].startswith("2026-09-29T10:15:00")


# ---- happy path -------------------------------------------------------------

@pytest.mark.parametrize("event_type", ["data.pipeline.completed", "data.pipeline.failed"])
def test_publishes_to_topic_named_after_event_type_and_marks_published(db, monkeypatch, event_type):
    producer = FakeProducer()
    monkeypatch.setattr(ke, "_producer", lambda: producer)

    result = ke.queue_and_publish(event_type, 42, {"run_id": 42, "status": "SUCCESS"})

    assert result["published"] is True
    assert len(producer.sent) == 1
    msg = producer.sent[0]
    assert msg["topic"] == event_type                       # topic name = event_type
    assert msg["key"] == msg["value"]["event_id"] == result["event_id"]
    assert msg["value"]["payload"] == {"run_id": 42, "status": "SUCCESS"}
    assert producer.closed
    (row,) = rows(db)
    assert row["status"] == "PUBLISHED"


# ---- unhappy paths: Kafka down ---------------------------------------------

def test_kafka_down_never_raises_and_event_stays_pending(db, monkeypatch):
    kafka_down(monkeypatch)

    result = ke.queue_and_publish("data.pipeline.completed", 1, {"run_id": 1})  # must not raise

    assert result["published"] is False and result["persisted"] is True
    (row,) = rows(db)
    assert row["status"] == "PENDING"
    assert row["attempts"] == 1
    assert "NoBrokersAvailable" in row["last_error"]


def test_kafka_send_failure_is_handled_and_producer_closed(db, monkeypatch):
    producer = FakeProducer(fail_send=True)
    monkeypatch.setattr(ke, "_producer", lambda: producer)

    result = ke.queue_and_publish("data.pipeline.failed", 2, {})

    assert result["published"] is False
    assert producer.closed
    assert rows(db)[0]["status"] == "PENDING"


def test_kafka_down_is_logged(db, monkeypatch, caplog):
    kafka_down(monkeypatch)
    with caplog.at_level("WARNING"):
        ke.queue_and_publish("data.pipeline.completed", 1, {})
    assert any("left PENDING for retry" in r.message for r in caplog.records)


def test_outbox_database_unreachable_does_not_raise(monkeypatch, caplog):
    def boom():
        raise ConnectionError("database unreachable")
    monkeypatch.setattr(ke, "get_engine", boom)

    with caplog.at_level("ERROR"):
        result = ke.queue_and_publish("data.pipeline.completed", 1, {})

    assert result["published"] is False and result["persisted"] is False
    assert any("EVENT LOST" in r.message for r in caplog.records)


# ---- retry ------------------------------------------------------------------

def test_pending_event_is_retried_and_published_unchanged_after_recovery(db, monkeypatch):
    kafka_down(monkeypatch)
    first = ke.queue_and_publish("data.pipeline.completed", 5, {"run_id": 5, "rows_inserted": 10})
    original_time = rows(db)[0]["occurred_at"]

    producer = FakeProducer()                     # Kafka is back
    monkeypatch.setattr(ke, "_producer", lambda: producer)
    out = ke.retry_pending_events()

    assert out["published"] == 1 and out["failed"] == 0
    (row,) = rows(db)
    assert row["status"] == "PUBLISHED"
    sent = producer.sent[0]["value"]
    assert sent["event_id"] == first["event_id"]             # same event, not a new one
    assert sent["occurred_at"] == original_time              # original time preserved
    assert sent["payload"] == {"run_id": 5, "rows_inserted": 10}
    assert sent["event_version"] == 1 and sent["producer"] == "etl"


def test_retry_with_kafka_still_down_keeps_events_pending(db, monkeypatch):
    kafka_down(monkeypatch)
    ke.queue_and_publish("data.pipeline.completed", 1, {})
    ke.queue_and_publish("data.pipeline.failed", 2, {})

    out = ke.retry_pending_events()          # must not raise

    assert out["published"] == 0
    assert all(r["status"] == "PENDING" for r in rows(db))


def test_retry_stops_after_first_failure_instead_of_timing_out_per_event(db, monkeypatch):
    kafka_down(monkeypatch)
    for i in range(5):
        ke.queue_and_publish("data.pipeline.completed", i, {})
    made = []
    producer = FakeProducer(fail_send=True)

    def factory():
        made.append(1)
        return producer
    monkeypatch.setattr(ke, "_producer", factory)

    out = ke.retry_pending_events()

    assert len(made) == 1                    # one producer for the whole batch
    assert out["attempted"] == 1 and out["failed"] == 1 and out["skipped"] == 4
    assert producer.closed
    attempts = sorted(r["attempts"] for r in rows(db))
    assert attempts == [1, 1, 1, 1, 2]       # 4 untouched by the retry, 1 tried once more


def test_broken_event_becomes_failed_after_max_attempts(db, monkeypatch):
    # RuntimeError represents a problem with the event itself, not Kafka being down.
    producer = FakeProducer(fail_send=True)
    monkeypatch.setattr(ke, "_producer", lambda: producer)
    ke.queue_and_publish("data.pipeline.completed", 1, {})

    for _ in range(3):
        out = ke.retry_pending_events()
        assert out["failed"] == 1

    row = rows(db)[0]
    assert row["status"] == "PENDING"
    assert row["attempts"] == 4

    out = ke.retry_pending_events()

    row = rows(db)[0]
    assert out["failed"] == 1
    assert row["status"] == "FAILED"
    assert row["attempts"] == 5

def test_retry_with_empty_outbox_does_not_touch_kafka(db, monkeypatch):
    monkeypatch.setattr(ke, "_producer", lambda: pytest.fail("producer must not be created"))
    assert ke.retry_pending_events() == {"attempted": 0, "published": 0, "failed": 0, "skipped": 0}


def test_already_published_events_are_not_resent(db, monkeypatch):
    producer = FakeProducer()
    monkeypatch.setattr(ke, "_producer", lambda: producer)
    ke.queue_and_publish("data.pipeline.completed", 1, {})
    producer.sent.clear()

    ke.retry_pending_events()

    assert producer.sent == []


def test_payload_survives_json_roundtrip(db, monkeypatch):
    kafka_down(monkeypatch)
    payload = {"run_id": 1, "task_states": {"dbt_build": "success"}, "note": "é✓"}
    ke.queue_and_publish("data.pipeline.completed", 1, payload)
    producer = FakeProducer()
    monkeypatch.setattr(ke, "_producer", lambda: producer)
    ke.retry_pending_events()
    assert json.loads(json.dumps(producer.sent[0]["value"]))["payload"] == payload




# ---- outages never dead-letter ---------------------------------------------
@pytest.mark.parametrize("make_error", [
    lambda: __import__("kafka.errors", fromlist=["x"]).KafkaTimeoutError("send timed out"),
    lambda: __import__("kafka.errors", fromlist=["x"]).NoBrokersAvailable(),
    lambda: ConnectionError("connection refused"),
])
def test_long_kafka_outage_never_marks_events_failed(db, monkeypatch, make_error):
    class DownProducer(FakeProducer):
        def send(self, topic, key=None, value=None):
            return FakeFuture(make_error())

    monkeypatch.setattr(ke, "_producer", lambda: DownProducer())
    ke.queue_and_publish("data.pipeline.completed", 1, {})

    for _ in range(ke.MAX_OUTBOX_ATTEMPTS * 4):
        ke.retry_pending_events()

    (row,) = rows(db)
    assert row["status"] == "PENDING"
    assert row["attempts"] == ke.MAX_OUTBOX_ATTEMPTS * 4 + 1


def test_producer_creation_failing_during_outage_never_marks_events_failed(db, monkeypatch):
    from kafka.errors import NoBrokersAvailable

    def down():
        raise NoBrokersAvailable()

    monkeypatch.setattr(ke, "_producer", down)
    ke.queue_and_publish("data.pipeline.completed", 1, {})

    for _ in range(ke.MAX_OUTBOX_ATTEMPTS * 4):
        ke.retry_pending_events()

    assert rows(db)[0]["status"] == "PENDING"


def test_event_published_after_outage_ends(db, monkeypatch):
    from kafka.errors import KafkaTimeoutError

    class DownProducer(FakeProducer):
        def send(self, topic, key=None, value=None):
            return FakeFuture(KafkaTimeoutError("send timed out"))

    monkeypatch.setattr(ke, "_producer", lambda: DownProducer())
    first = ke.queue_and_publish("data.pipeline.completed", 1, {"run_id": 1})

    for _ in range(ke.MAX_OUTBOX_ATTEMPTS * 2):
        ke.retry_pending_events()

    producer = FakeProducer()
    monkeypatch.setattr(ke, "_producer", lambda: producer)
    out = ke.retry_pending_events()

    assert out["published"] == 1
    assert producer.sent[0]["value"]["event_id"] == first["event_id"]
    assert rows(db)[0]["status"] == "PUBLISHED"


def test_message_too_large_is_dead_lettered(db, monkeypatch):
    from kafka.errors import MessageSizeTooLargeError

    class RejectingProducer(FakeProducer):
        def send(self, topic, key=None, value=None):
            return FakeFuture(MessageSizeTooLargeError("too large"))

    monkeypatch.setattr(ke, "_producer", lambda: RejectingProducer())
    ke.queue_and_publish("data.pipeline.completed", 1, {})

    for _ in range(ke.MAX_OUTBOX_ATTEMPTS - 1):
        ke.retry_pending_events()

    row = rows(db)[0]
    assert row["status"] == "FAILED"
    assert row["attempts"] == ke.MAX_OUTBOX_ATTEMPTS
    assert "MessageSizeTooLargeError" in row["last_error"]
