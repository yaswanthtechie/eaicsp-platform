import json
import os
from unittest.mock import MagicMock

import pytest

from live_monitor import (
    UNKNOWN_PRODUCER,
    Report,
    check_message,
    load_expected_producers,
    load_validators,
    read_topic,
)

EXAMPLES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "events", "examples"
)
EXAMPLE_FILES = sorted(f for f in os.listdir(EXAMPLES_DIR) if f.endswith(".json"))


@pytest.fixture(scope="module")
def validators():
    return load_validators()


def load_example(name):
    with open(os.path.join(EXAMPLES_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def as_bytes(event):
    return json.dumps(event).encode("utf-8")


@pytest.mark.parametrize("name", EXAMPLE_FILES)
def test_every_contract_example_passes(name, validators):
    event = load_example(name)
    result = check_message(event["event_type"], as_bytes(event), validators)
    assert result.problems == []
    assert result.producer == event["producer"]


def test_missing_payload_field_is_reported(validators):
    event = load_example("supplierportal.shipment.dispatched.v1.json")
    del event["payload"]["carrier"]

    result = check_message("supplierportal.shipment.dispatched", as_bytes(event), validators)

    assert result.producer == "supplier-portal"
    assert any("carrier" in p for p in result.problems)


def test_bad_uuid_format_is_reported(validators):
    event = load_example("eta.shipment.predicted.v1.json")
    event["event_id"] = "not-a-uuid"

    result = check_message("eta.shipment.predicted", as_bytes(event), validators)

    assert any(p.startswith("event_id:") for p in result.problems)


def test_event_type_must_match_topic(validators):
    event = load_example("eta.shipment.predicted.v1.json")

    result = check_message("supplierrisk.score.changed", as_bytes(event), validators)

    assert any("does not match topic" in p for p in result.problems)


def test_unknown_version_has_no_schema(validators):
    event = load_example("eta.shipment.predicted.v1.json")
    event["event_version"] = 2

    result = check_message("eta.shipment.predicted", as_bytes(event), validators)

    assert result.problems == ["no schema contracts/events/eta.shipment.predicted.v2.json"]


def test_invalid_json_goes_to_unknown_producer(validators):
    result = check_message("eta.shipment.predicted", b"{not json", validators)

    assert result.producer == f"{UNKNOWN_PRODUCER}, topic owner ETA"
    assert result.problems[0].startswith("not valid JSON")


def test_tombstone_is_reported(validators):
    result = check_message("eta.shipment.predicted", None, validators)

    assert result.problems == ["empty message value (tombstone)"]


def test_report_groups_violations_by_producer(validators):
    good = load_example("eta.shipment.predicted.v1.json")
    bad = load_example("supplierportal.shipment.dispatched.v1.json")
    del bad["payload"]["carrier"]

    report = Report()
    report.add("eta.shipment.predicted", 0, 1,
               check_message("eta.shipment.predicted", as_bytes(good), validators))
    report.add("supplierportal.shipment.dispatched", 0, 7,
               check_message("supplierportal.shipment.dispatched", as_bytes(bad), validators))

    assert report.messages == {"eta-prediction": 1, "supplier-portal": 1}
    assert report.bad == {"supplier-portal": 1}
    assert report.total_bad == 1

    markdown = report.to_markdown("localhost:29092", validators)
    assert "| supplier-portal | 1 | 1 |" in markdown
    assert "| eta-prediction | 1 | 0 |" in markdown
    assert "`supplierportal.shipment.dispatched` partition 0 offset 7" in markdown
    # Blueprint topics with no schema file are called out.
    assert "`inventory.stock.low`" in markdown


def test_string_event_version_still_validates_against_v1(validators):
    event = load_example("supplierportal.shipment.dispatched.v1.json")
    event["event_version"] = "1"
    del event["payload"]["carrier"]

    result = check_message("supplierportal.shipment.dispatched", as_bytes(event), validators)

    assert not any("no schema" in p for p in result.problems)
    assert any(p.startswith("event_version:") for p in result.problems)
    assert any("carrier" in p for p in result.problems)


def test_non_numeric_event_version_is_reported(validators):
    event = load_example("eta.shipment.predicted.v1.json")
    event["event_version"] = "v1"

    result = check_message("eta.shipment.predicted", as_bytes(event), validators)

    assert result.problems == ["event_version must be an integer, got 'v1'"]


def test_wrong_producer_on_a_topic_is_reported(validators):
    event = load_example("supplierportal.shipment.dispatched.v1.json")
    event["producer"] = "inventory-service"

    result = check_message(
        "supplierportal.shipment.dispatched", as_bytes(event), validators,
        load_expected_producers(),
    )

    assert any("is not this topic's producer 'supplier-portal'" in p for p in result.problems)


def test_pipe_in_producer_does_not_break_the_table(validators):
    event = load_example("eta.shipment.predicted.v1.json")
    event["producer"] = "eta|prediction"

    report = Report()
    report.add("eta.shipment.predicted", 0, 1,
               check_message("eta.shipment.predicted", as_bytes(event), validators))

    assert "| eta\\|prediction | 1 |" in report.to_markdown("localhost:29092", validators)


def _fake_message(partition, offset, value=b"{}"):
    message = MagicMock()
    message.error.return_value = None
    message.partition.return_value = partition
    message.offset.return_value = offset
    message.value.return_value = value
    return message


def test_read_topic_reads_up_to_the_end_offset_and_never_commits():
    consumer = MagicMock()
    topic_metadata = MagicMock(error=None, partitions={0: None})
    consumer.list_topics.return_value.topics = {"eta.shipment.predicted": topic_metadata}
    consumer.get_watermark_offsets.return_value = (0, 2)  # offsets 0 and 1
    consumer.poll.side_effect = [_fake_message(0, 0), _fake_message(0, 1), AssertionError("read past end")]

    status = [None]
    messages = list(read_topic(consumer, "eta.shipment.predicted", 1.0, status))

    assert [m.offset() for m in messages] == [0, 1]
    assert status == ["done"]
    consumer.commit.assert_not_called()
    consumer.unassign.assert_called_once()


def test_read_topic_stops_on_partition_eof_even_if_last_offset_never_arrives():
    from confluent_kafka import KafkaError

    consumer = MagicMock()
    consumer.list_topics.return_value.topics = {
        "eta.shipment.predicted": MagicMock(error=None, partitions={0: None})
    }
    consumer.get_watermark_offsets.return_value = (0, 3)  # offset 2 never arrives
    eof = MagicMock()
    eof.error.return_value.code.return_value = KafkaError._PARTITION_EOF
    eof.partition.return_value = 0
    consumer.poll.side_effect = [
        _fake_message(0, 0), _fake_message(0, 1), eof, AssertionError("read past end"),
    ]

    status = [None]
    messages = list(read_topic(consumer, "eta.shipment.predicted", 1.0, status))

    assert [m.offset() for m in messages] == [0, 1]
    assert status == ["done"]


def test_read_topic_reports_missing_topic():
    consumer = MagicMock()
    consumer.list_topics.return_value.topics = {}

    status = [None]
    assert list(read_topic(consumer, "inventory.stock.low", 1.0, status)) == []
    assert status == ["missing"]


def test_read_topic_reports_empty_topic():
    consumer = MagicMock()
    consumer.list_topics.return_value.topics = {
        "inventory.po.approved": MagicMock(error=None, partitions={0: None})
    }
    consumer.get_watermark_offsets.return_value = (5, 5)

    status = [None]
    assert list(read_topic(consumer, "inventory.po.approved", 1.0, status)) == []
    assert status == ["empty"]
    consumer.assign.assert_not_called()


def test_run_keeps_going_when_one_topic_errors(monkeypatch):
    import confluent_kafka

    from live_monitor import CATALOG, run

    consumer = MagicMock()
    consumer.list_topics.side_effect = lambda topic=None, timeout=None: (
        _raise(confluent_kafka.KafkaException("boom"))
        if topic == "eta.shipment.predicted"
        else MagicMock(topics={})
    )
    monkeypatch.setattr(confluent_kafka, "Consumer", lambda config: consumer)

    report, _ = run("localhost:29092", timeout=1.0)

    assert [t for t, _ in report.errored_topics] == ["eta.shipment.predicted"]
    assert len(report.missing_topics) == len(CATALOG) - 1
    consumer.close.assert_called_once()


def _raise(exc):
    raise exc


@pytest.mark.integration
def test_live_kafka_smoke():
    """Needs the stack up (make up). Run with: pytest -m integration"""
    from confluent_kafka import KafkaException

    from live_monitor import CATALOG, run

    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
    try:
        report, _ = run(bootstrap, timeout=5.0)
    except KafkaException as exc:
        pytest.fail(f"Kafka not reachable at {bootstrap}. Is `make up` running? {exc}")

    # Every catalog topic must land in exactly one bucket.
    buckets = [
        report.read_topics,
        report.missing_topics,
        report.empty_topics,
        report.unfinished_topics,
        [topic for topic, _ in report.errored_topics],
    ]
    for topic in CATALOG:
        assert sum(topic in bucket for bucket in buckets) == 1, topic
    assert report.errored_topics == []