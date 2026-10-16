from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from src.stream_eval import RUNS, evaluate_events, run_once
from src.stream_events import build_anomaly_event
from src.stream_model import train_stream_model
from src.stream_simulator import FEATURES, build_stream


START = datetime(2026, 3, 1, tzinfo=UTC)
STEP = timedelta(minutes=5)


def t(i):
    return START + i * STEP


def event(sensor, ws, we):

    return build_anomaly_event(
        sensor_id=sensor,
        window_start=t(ws),
        window_end=t(we),
        first_flag_time=t(ws),
        confirmed_time=t(ws + 1),
        peak_time=t(ws),
        peak_score=1.0,
        threshold=0.5,
        n_flagged=2,
        closed_by="quiet",
        top_features=[{"feature": "power", "contribution": 1.0, "shap_value": 0.1, "direction": "high"}],
        model_version="test",
    )


def episode(sensor, kind, a, b):

    return {
        "sensor_id": sensor,
        "kind": kind,
        "start_idx": a,
        "end_idx": b,
        "start_time": t(a),
        "end_time": t(b),
    }


EPISODES = [episode("s1", "a", 10, 14), episode("s1", "b", 50, 50)]


def test_known_answer():

    m = evaluate_events(
        [event("s1", 11, 13), event("s1", 80, 82)], EPISODES, {"s1": 100}
    )

    assert m["true_episodes"] == 2
    assert m["detected"] == 1
    assert m["published_events"] == 2
    assert m["false_alarm_events"] == 1
    assert m["event_precision"] == 0.5
    assert m["event_recall"] == 0.5
    assert m["median_delay_first_flag_min"] == 5.0
    assert m["median_delay_confirmed_min"] == 10.0
    assert m["episode_cost"] == 1 * 500 + 1 * 2
    assert m["by_kind"] == {"a": (1, 1), "b": (0, 1)}


def test_fragmentation_is_visible():

    m = evaluate_events(
        [event("s1", 11, 11), event("s1", 13, 13)], EPISODES, {"s1": 100}
    )

    assert m["event_precision"] == 1.0
    assert m["events_per_detected_episode"] == 2.0


def test_no_events():

    m = evaluate_events([], EPISODES, {"s1": 100})

    assert m["event_precision"] is None
    assert m["event_recall"] == 0.0
    assert m["missed"] == 2


@pytest.fixture(scope="module")
def setup():

    readings, episodes = build_stream()
    model = train_stream_model()

    X = np.array([[r[f] for f in FEATURES] for r in readings])
    scores = model.score_batch(X)

    n = {}
    for r in readings:
        n[r["sensor_id"]] = n.get(r["sensor_id"], 0) + 1

    return readings, scores, episodes, model, n


def test_end_to_end_invariants(setup):

    readings, scores, episodes, model, n = setup

    results = {}

    for label, min_flagged, tuner_on in RUNS:

        metrics, processor, publisher = run_once(
            readings, scores, episodes, model, min_flagged, tuner_on, n
        )

        assert len(publisher.events) == processor.detector.episodes_emitted
        assert all(e["payload"]["top_features"] for e in publisher.events)

        results[label] = metrics

    # Same grouping, same frozen threshold: min=2 can only confirm a subset.
    assert results["D"]["published_events"] <= results["C"]["published_events"]
    assert results["D"]["false_alarm_events"] <= results["C"]["false_alarm_events"]
    assert results["D"]["detected"] <= results["C"]["detected"]
    assert results["C"]["threshold_start"] == results["C"]["threshold_end"]