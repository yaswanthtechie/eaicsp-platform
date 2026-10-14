import json
from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.stream_events import (
    EVENT_TYPE,
    EVENT_VERSION,
    PRODUCER,
    build_anomaly_event,
    event_key,
    make_episode_id,
    to_utc_iso,
)


T0 = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)


def _kwargs(**overrides):

    base = dict(
        sensor_id="wh1-s1",
        window_start=T0,
        window_end=T0 + timedelta(minutes=20),
        first_flag_time=T0,
        confirmed_time=T0 + timedelta(minutes=5),
        peak_time=T0 + timedelta(minutes=10),
        peak_score=0.42,
        threshold=0.10,
        n_flagged=5,
        closed_by="quiet",
        top_features=[
            {"feature": "temperature", "contribution": 0.8, "direction": "high"},
            {"feature": "power", "contribution": 0.2, "direction": "high"},
        ],
        model_version="stream-1.0",
    )

    base.update(overrides)

    return base


def test_envelope_fields_match_inventory_schema():

    event = build_anomaly_event(**_kwargs())

    assert set(event) == {
        "event_id",
        "event_type",
        "producer",
        "occurred_at",
        "event_version",
        "trace_id",
        "payload",
    }

    assert event["event_type"] == EVENT_TYPE == "iot.anomaly.detected"
    assert event["producer"] == PRODUCER
    assert event["event_version"] == EVENT_VERSION == "1.0"
    assert event["trace_id"] is None


def test_occurred_at_is_utc_wall_clock():

    event = build_anomaly_event(**_kwargs())

    parsed = datetime.fromisoformat(event["occurred_at"])

    assert parsed.utcoffset() == timedelta(0)

    # Creation time, not the simulated 2026-01-01 window.
    assert parsed != T0


def test_event_ids_are_unique_and_injectable():

    first = build_anomaly_event(**_kwargs())
    second = build_anomaly_event(**_kwargs())

    assert first["event_id"] != second["event_id"]

    fixed = build_anomaly_event(**_kwargs(event_id="abc"))

    assert fixed["event_id"] == "abc"


def test_payload_content_and_json_serializable():

    event = build_anomaly_event(**_kwargs())
    payload = event["payload"]

    assert payload["sensor_id"] == "wh1-s1"
    assert payload["window_start"] == "2026-01-01T10:00:00+00:00"
    assert payload["window_end"] == "2026-01-01T10:20:00+00:00"
    assert payload["peak_score"] == 0.42
    assert payload["n_flagged"] == 5
    assert payload["closed_by"] == "quiet"
    assert payload["severe"] is False
    assert payload["top_features"][0]["feature"] == "temperature"

    json.dumps(event)


def test_episode_id_is_deterministic():

    assert make_episode_id("wh1-s1", T0) == make_episode_id("wh1-s1", T0)
    assert make_episode_id("wh1-s1", T0) != make_episode_id("wh1-s2", T0)

    event = build_anomaly_event(**_kwargs())

    assert event["payload"]["episode_id"] == make_episode_id("wh1-s1", T0)


def test_naive_datetime_is_treated_as_utc():

    assert to_utc_iso(datetime(2026, 1, 1, 10, 0)) == "2026-01-01T10:00:00+00:00"


def test_other_timezone_is_converted_to_utc():

    ist = timezone(timedelta(hours=5, minutes=30))

    assert (
        to_utc_iso(datetime(2026, 1, 1, 15, 30, tzinfo=ist))
        == "2026-01-01T10:00:00+00:00"
    )


def test_partition_key_is_sensor_id():

    assert event_key(build_anomaly_event(**_kwargs())) == "wh1-s1"


def test_shutdown_flush_is_allowed():

    event = build_anomaly_event(**_kwargs(closed_by="shutdown"))

    assert event["payload"]["closed_by"] == "shutdown"


@pytest.mark.parametrize(
    "overrides",
    [
        {"sensor_id": ""},
        {"closed_by": "timeout"},
        {"window_end": T0 - timedelta(minutes=1)},
        {"peak_score": float("nan")},
        {"threshold": float("inf")},
        {"n_flagged": 0},
        {"top_features": []},
        {"top_features": [{"feature": "power", "contribution": 1.5, "direction": "high"}]},
        {"top_features": [{"feature": "power", "contribution": 0.5, "direction": "up"}]},
        {"top_features": [{"feature": "", "contribution": 0.5, "direction": "high"}]},
    ],
)
def test_invalid_input_is_rejected(overrides):

    with pytest.raises(ValueError):
        build_anomaly_event(**_kwargs(**overrides))