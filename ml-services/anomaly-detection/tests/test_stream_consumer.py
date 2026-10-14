import json
from datetime import UTC, datetime

from src.stream_consumer import (
    JsonlEventLog,
    MultiPublisher,
    load_settings,
    parse_message,
    to_line_protocol,
)
from src.stream_processor import InMemoryPublisher


def test_settings_defaults():

    s = load_settings({})

    assert s["bootstrap_servers"] == "localhost:9092"
    assert s["readings_topic"] == "iot.sensor.reading"
    assert s["events_topic"] == "iot.anomaly.detected"
    assert s["influx_org"] == "eaicsp"
    assert s["influx_bucket"] == "iot_sensors"
    assert s["influx_token"] == ""


def test_settings_override():

    s = load_settings({"KAFKA_BOOTSTRAP_SERVERS": "kafka:29092", "INFLUXDB_TOKEN": "t"})

    assert s["bootstrap_servers"] == "kafka:29092"
    assert s["influx_token"] == "t"


def test_parse_message():

    message = json.dumps(
        {
            "sensor_id": "wh1-s1",
            "timestamp": "2026-03-01T00:00:00+00:00",
            "temperature": 22.5,
            "humidity": 45.0,
            "door_open": 0,
            "power": 300.0,
        }
    ).encode()

    reading = parse_message(message)

    assert reading["timestamp"] == datetime(2026, 3, 1, tzinfo=UTC)
    assert reading["temperature"] == 22.5


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

    multi.publish({"a": 1})
    multi.publish({"a": 2})
    multi.close()

    lines = (tmp_path / "events.jsonl").read_text().splitlines()

    assert [json.loads(x) for x in lines] == [{"a": 1}, {"a": 2}]
    assert memory.events == [{"a": 1}, {"a": 2}]