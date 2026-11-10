import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from src.demo_anomaly import (
    CLOSING_GAP,
    COOLDOWN,
    EPISODE_READINGS,
    build_demo_readings,
    load_state,
    pick_sensor,
    save_state,
)
from src.sensor_config import generate_sensors, sensor_map
from src.stream_consumer import GAP, build_processor
from src.stream_model import train_stream_model
from src.stream_processor import InMemoryPublisher, InMemoryWriter

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = ROOT / "contracts" / "events" / "iot.anomaly.detected.v1.json"

END = datetime(2026, 10, 28, 10, 0, 0, tzinfo=UTC)
SENSORS = generate_sensors(["WH-BLR-01", "WH-DEL-01"], 2)


@pytest.fixture(scope="module")
def model():
    return train_stream_model()


def test_closing_gap_is_longer_than_the_detector_gap():

    assert CLOSING_GAP > GAP


def test_readings_are_ordered_and_end_at_the_requested_time():

    readings, _ = build_demo_readings("WH-BLR-01-S1", end=END)
    times = [r["timestamp"] for r in readings]

    assert len(readings) == EPISODE_READINGS + 1
    assert times == sorted(times)
    assert len(set(times)) == len(times)
    assert times[-1] == END
    assert times[-1] - times[-2] == CLOSING_GAP


def test_pick_sensor_prefers_unused_and_respects_cooldown():

    now = END.timestamp()
    used = {s["sensor_id"]: now for s in SENSORS[:-1]}

    assert pick_sensor(SENSORS, used, END) == SENSORS[-1]["sensor_id"]

    used[SENSORS[-1]["sensor_id"]] = now - 1

    with pytest.raises(RuntimeError):
        pick_sensor(SENSORS, used, END)

    later = END + COOLDOWN + timedelta(seconds=1)

    assert pick_sensor(SENSORS, used, later) in {s["sensor_id"] for s in SENSORS}


def test_state_round_trip_and_bad_file(tmp_path):

    path = tmp_path / "state.json"

    assert load_state(path) == {}

    save_state({"a": 1.5}, path)

    assert load_state(path) == {"a": 1.5}

    path.write_text("not json", encoding="utf-8")

    assert load_state(path) == {}


def test_demo_episode_gives_exactly_one_contract_valid_event(model):

    readings, expected = build_demo_readings("WH-BLR-01-S1", end=END)

    publisher = InMemoryPublisher()
    processor = build_processor(
        {}, model, InMemoryWriter(), publisher, sensor_map(SENSORS)
    )

    for reading in readings:
        processor.handle(reading)

    assert len(publisher.events) == 1

    event = publisher.events[0]
    payload = event["payload"]

    assert payload["episode_id"] == expected
    assert payload["n_flagged"] == EPISODE_READINGS
    assert payload["closed_by"] == "quiet"
    assert payload["warehouse_id"] == "WH-BLR-01"
    assert payload["top_features"][0]["feature"] == "temperature"

    validator = Draft202012Validator(
        json.loads(SCHEMA.read_text(encoding="utf-8")),
        format_checker=FormatChecker(),
    )

    assert list(validator.iter_errors(event)) == []