import json
from datetime import datetime

from app.core.config import SERVICE_NAME
from app.services import kafka_producer


FIELDS = {
    "supplier_name": "ACME LTD",
    "country": "India",
    "old_status": "CLEAR",
    "new_status": "BLOCK",
    "matched_list": ["OFAC"],
    "reason": "Matched name ACME LTD on OFAC",
    "screening_run_id": "run-1",
}


class _RecordingProducer:
    def __init__(self):
        self.sent = []

    def produce(self, topic, key, value, callback):
        self.sent.append((topic, key, value))
        callback(None, None)

    def flush(self, timeout):
        return 0


class _DownProducer:
    def produce(self, *args, **kwargs):
        raise BufferError("Local: Queue full")

    def flush(self, timeout):
        return 0


class _UnacknowledgedProducer:
    def produce(self, topic, key, value, callback):
        pass

    def flush(self, timeout):
        return 1


def test_event_uses_standard_envelope(monkeypatch):
    producer = _RecordingProducer()
    monkeypatch.setattr(
        kafka_producer,
        "get_kafka_producer",
        lambda: producer,
    )

    assert (
        kafka_producer.publish_supplier_status_changed(**FIELDS)
        is True
    )
    assert len(producer.sent) == 1

    topic, key, value = producer.sent[0]
    event = json.loads(value)

    assert set(event) == {
        "event_id",
        "event_type",
        "event_version",
        "occurred_at",
        "producer",
        "payload",
    }
    assert (
        topic
        == event["event_type"]
        == "compliance.supplier.status_changed"
    )
    assert event["event_version"] == 1
    assert event["producer"] == SERVICE_NAME

    occurred_at = datetime.fromisoformat(
        event["occurred_at"]
    )
    assert occurred_at.utcoffset().total_seconds() == 0

    assert event["payload"] == FIELDS
    assert key == "ACME LTD"


def test_kafka_down_returns_false_instead_of_raising(monkeypatch):
    monkeypatch.setattr(
        kafka_producer,
        "get_kafka_producer",
        lambda: _DownProducer(),
    )

    assert (
        kafka_producer.publish_supplier_status_changed(**FIELDS)
        is False
    )


def test_unacknowledged_message_returns_false(monkeypatch):
    monkeypatch.setattr(
        kafka_producer,
        "get_kafka_producer",
        lambda: _UnacknowledgedProducer(),
    )

    assert (
        kafka_producer.publish_supplier_status_changed(**FIELDS)
        is False
    )


def test_kafka_producer_enables_idempotence(monkeypatch):
    captured = {}

    class _FakeProducer:
        def __init__(self, config):
            captured.update(config)

    monkeypatch.setattr(
        kafka_producer,
        "Producer",
        _FakeProducer,
    )
    monkeypatch.setattr(
        kafka_producer,
        "_producer",
        None,
    )

    kafka_producer.get_kafka_producer()

    assert captured["enable.idempotence"] is True
