import uuid
import pytest
from app.core import event_publisher

def test_build_event_contains_standard_envelope():
    event = event_publisher.build_event(
        "platform.user.locked",
        {"user_id": 123},
    )

    assert set(event.keys()) == {
        "event_id",
        "event_type",
        "event_version",
        "occurred_at",
        "producer",
        "payload",
    }

    assert event["event_type"] == (
        "platform.user.locked"
    )

    assert event["event_version"] == 1

    assert event["producer"] == (
        "platform-service"
    )

    assert event["payload"] == {
        "user_id": 123
    }


def test_event_id_is_valid_uuid():
    event = event_publisher.build_event(
        "platform.user.locked",
        {"user_id": 123},
    )

    parsed_uuid = uuid.UUID(
        event["event_id"]
    )

    assert str(parsed_uuid) == event["event_id"]


def test_event_timestamp_is_utc():
    event = event_publisher.build_event(
        "platform.user.locked",
        {"user_id": 123},
    )

    assert event["occurred_at"].endswith("Z")


def test_event_ids_are_unique():
    event1 = event_publisher.build_event(
        "platform.user.locked",
        {"user_id": 123},
    )

    event2 = event_publisher.build_event(
        "platform.user.locked",
        {"user_id": 123},
    )

    assert event1["event_id"] != event2["event_id"]


def test_event_payload_is_preserved():
    payload = {
        "user_id": 123,
        "reason": "too_many_failed_logins",
    }

    event = event_publisher.build_event(
        "platform.user.locked",
        payload,
    )

    assert event["payload"] == payload

def test_publish_event_uses_event_type_as_topic(
    monkeypatch,
):
    captured = {}

    class FakeFuture:
        def get(self, timeout):
            captured["timeout"] = timeout
            return True

    class FakeProducer:
        def send(self, topic, value):
            captured["topic"] = topic
            captured["value"] = value
            return FakeFuture()

    monkeypatch.setattr(
        event_publisher,
        "_get_producer",
        lambda: FakeProducer(),
    )

    result = event_publisher.publish_event(
        "platform.user.locked",
        {"user_id": 123},
    )

    assert captured["topic"] == "platform.user.locked"
    assert captured["value"] == result
    assert captured["timeout"] == event_publisher.PUBLISH_TIMEOUT_SECONDS


def test_publish_event_never_raises_when_kafka_is_down(monkeypatch):
    """A Kafka outage is logged and returns None; it never raises."""
    from kafka.errors import KafkaTimeoutError

    class DownProducer:
        def send(self, topic, value):
            raise KafkaTimeoutError("Kafka is down")

    monkeypatch.setattr(event_publisher, "_get_producer", lambda: DownProducer())
    monkeypatch.setattr(event_publisher, "_reset_producer", lambda: None)

    result = event_publisher.publish_event(
        "platform.user.locked",
        {"user_id": 123},
    )

    assert result is None

def test_empty_event_type_is_rejected():
    with pytest.raises(ValueError):
        event_publisher.build_event(
            "",
            {"user_id": 123},
        )


def test_non_dict_payload_is_rejected():
    with pytest.raises(TypeError):
        event_publisher.build_event(
            "platform.user.locked",
            "invalid",
        )