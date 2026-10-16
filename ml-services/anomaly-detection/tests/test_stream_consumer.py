import json
from datetime import UTC, datetime

import pytest

from src.stream_consumer import (
    InvalidReading,
    JsonlEventLog,
    MultiPublisher,
    load_settings,
    parse_message,
    to_line_protocol,
)
from src.stream_processor import InMemoryPublisher


GOOD = {
    "sensor_id": "wh1-s1",
    "timestamp": "2026-03-01T00:00:00+00:00",
    "temperature": 22.0,
    "humidity": 45.0,
    "door_open": 0,
    "power": 300.0,
}


def test_settings_defaults():

    s = load_settings({"INFLUXDB_TOKEN": "t"})

    assert s["bootstrap_servers"] == "localhost:9092"
    assert s["readings_topic"] == "iot.sensor.reading"
    assert s["events_topic"] == "iot.anomaly.detected"
    assert s["influx_org"] == "eaicsp"
    assert s["influx_bucket"] == "iot_sensors"
    assert s["influx_token"] == "t"


def test_settings_override():

    s = load_settings(
        {"KAFKA_BOOTSTRAP_SERVERS": "kafka:29092", "INFLUXDB_TOKEN": "t"}
    )

    assert s["bootstrap_servers"] == "kafka:29092"


def test_settings_require_token():

    with pytest.raises(RuntimeError):
        load_settings({})


def test_parse_message():

    reading = parse_message(json.dumps(GOOD).encode())

    assert reading["timestamp"] == datetime(2026, 3, 1, tzinfo=UTC)
    assert reading["temperature"] == 22.0
    assert reading["sensor_id"] == "wh1-s1"


@pytest.mark.parametrize(
    "raw",
    [
        b"not json",
        b"\xff\xfe",
        b"[1, 2, 3]",
        json.dumps({k: v for k, v in GOOD.items() if k != "timestamp"}).encode(),
        json.dumps({**GOOD, "temperature": "nan"}).encode(),
        json.dumps({**GOOD, "power": "abc"}).encode(),
        json.dumps({**GOOD, "door_open": 3}).encode(),
        json.dumps({**GOOD, "timestamp": "yesterday"}).encode(),
        json.dumps({**GOOD, "sensor_id": "  "}).encode(),
    ],
)
def test_invalid_messages_raise_invalid_reading(raw):

    with pytest.raises(InvalidReading):
        parse_message(raw)


def test_line_protocol():

    reading = {
        "sensor_id": "wh1-s1",
        "timestamp": datetime(2026, 3, 1, tzinfo=UTC),
        "temperature": 22.5,
        "humidity": 45.0,
        "door_open": 1,
        "power": 300.0,
    }

    assert to_line_protocol(reading, -0.1, True) == (
        "warehouse_sensor,sensor_id=wh1-s1 "
        "temperature=22.5,humidity=45.0,door_open=1i,power=300.0,"
        "anomaly_score=-0.1,is_flagged=1i 1772323200"
    )


def test_jsonl_log_and_multi_publisher(tmp_path):

    memory = InMemoryPublisher()
    log = JsonlEventLog(tmp_path / "events.jsonl")
    multi = MultiPublisher(memory, log)

    e1 = {"payload": {"episode_id": "a"}}
    e2 = {"payload": {"episode_id": "b"}}

    multi.publish(e1)
    multi.publish(e2)
    multi.close()

    lines = (tmp_path / "events.jsonl").read_text().splitlines()

    assert [json.loads(x) for x in lines] == [e1, e2]
    assert memory.events == [e1, e2]


def test_jsonl_log_skips_duplicates_across_runs(tmp_path):

    path = tmp_path / "events.jsonl"
    event = {"payload": {"episode_id": "a"}}

    first = JsonlEventLog(path)
    first.publish(event)
    first.publish(event)
    first.close()

    second = JsonlEventLog(path)
    second.publish(event)
    second.close()

    assert len(path.read_text().splitlines()) == 1