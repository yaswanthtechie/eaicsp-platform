import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from src.episode_detector import EpisodeDetector
from src.sensor_config import generate_sensors, sensor_map
from src.stream_events import build_anomaly_event, severity_for
from src.stream_processor import InMemoryPublisher, InMemoryWriter, StreamProcessor

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = ROOT / "contracts" / "events" / "iot.anomaly.detected.v1.json"
EXAMPLE = ROOT / "contracts" / "events" / "examples" / "iot.anomaly.detected.v1.json"

T0 = datetime(2026, 3, 1, tzinfo=UTC)
STEP = timedelta(minutes=5)

FEATURE = {
    "feature": "power",
    "contribution": 1.0,
    "shap_value": 0.1,
    "direction": "high",
}


@pytest.fixture(scope="module")
def validator():

    assert SCHEMA.is_file(), f"contract not found: {SCHEMA}"

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)

    return Draft202012Validator(schema, format_checker=FormatChecker())


class FakeModel:

    version = "fake"

    def explain(self, reading, top_k=3):
        return [
            {
                "feature": "temperature",
                "contribution": 0.9,
                "shap_value": 0.07,
                "direction": "high",
            },
            {
                "feature": "door_open",
                "contribution": 0.1,
                "shap_value": 0.008,
                "direction": "low",
            },
        ]


class StubTuner:

    threshold = 1.0

    def observe(self, score):
        return None


def make_processor():

    sensors = generate_sensors(["WH-BLR-01"], 2)
    publisher = InMemoryPublisher()
    writer = InMemoryWriter()

    processor = StreamProcessor(
        FakeModel(),
        StubTuner(),
        EpisodeDetector(gap=3 * STEP, scale=1.0, min_flagged_readings=2),
        writer,
        publisher,
        use_tuner=False,
        sensor_map=sensor_map(sensors),
    )

    return processor, publisher, writer


def feed(processor, scores, sensor="WH-BLR-01-S1"):

    for i, score in enumerate(scores):
        processor.handle(
            {"sensor_id": sensor, "timestamp": T0 + i * STEP}, score=score
        )


def _event(**overrides):

    params = dict(
        sensor_id="WH-BLR-01-S1",
        window_start=T0,
        window_end=T0,
        first_flag_time=T0,
        confirmed_time=T0,
        peak_time=T0,
        peak_score=1.0,
        threshold=0.5,
        n_flagged=1,
        closed_by="quiet",
        top_features=[FEATURE],
        model_version="t",
    )
    params.update(overrides)

    return build_anomaly_event(**params)


def test_contract_example_is_valid(validator):

    example = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    assert list(validator.iter_errors(example)) == []


def test_published_event_matches_contract(validator):

    processor, publisher, _ = make_processor()
    feed(processor, [10.0] * 12 + [0.0] * 5)

    assert len(publisher.events) == 1

    event = publisher.events[0]

    assert list(validator.iter_errors(event)) == []
    assert event["payload"]["warehouse_id"] == "WH-BLR-01"
    assert event["payload"]["severity"] == "critical"
    assert event["payload"]["message"].startswith("Temperature unusually high")


def test_shutdown_flush_event_matches_contract(validator):

    processor, publisher, _ = make_processor()
    feed(processor, [2.0, 2.0, 2.0])

    processor.finish()

    assert len(publisher.events) == 1
    assert list(validator.iter_errors(publisher.events[0])) == []
    assert publisher.events[0]["payload"]["closed_by"] == "shutdown"
    assert publisher.events[0]["payload"]["severity"] == "medium"


def test_event_without_warehouse_is_rejected_by_contract(validator):

    assert list(validator.iter_errors(_event())) != []


def test_event_with_warehouse_passes_contract(validator):

    assert list(validator.iter_errors(_event(warehouse_id="WH-DEL-01"))) == []


def test_unknown_sensor_is_skipped_not_published():

    processor, publisher, writer = make_processor()
    feed(processor, [10.0] * 3, sensor="wh1-s1")

    assert processor.skipped_unknown == 3
    assert writer.rows == []
    assert processor.finish() == []
    assert publisher.events == []


@pytest.mark.parametrize(
    "severe,n,expected",
    [
        (True, 10, "critical"),
        (True, 9, "high"),
        (True, 1, "high"),
        (False, 3, "medium"),
        (False, 2, "low"),
        (False, 50, "medium"),
    ],
)
def test_severity_rule(severe, n, expected):

    assert severity_for(severe, n) == expected


def test_bad_warehouse_id_is_rejected():

    with pytest.raises(ValueError):
        _event(warehouse_id="WH1")