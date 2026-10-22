import joblib
import numpy as np
import pytest
from datetime import UTC, datetime, timedelta

from src.auto_threshold import SignificanceThresholdTuner, robust_scale
from src.episode_detector import EpisodeDetector
from src.stream_eval import evaluate_events
from src.stream_events import build_anomaly_event
from src.stream_model import (
    MODEL_VERSION,
    load_stream_model,
    save_stream_model,
    train_stream_model,
)
from src.stream_processor import InMemoryPublisher, InMemoryWriter, StreamProcessor
from src.stream_simulator import FEATURES, START_TIME, STEP, build_stream


@pytest.fixture(scope="module")
def stream_model():
    return train_stream_model()


class FakeModel:

    version = "fake"

    def score_one(self, reading):
        return 0.0

    def explain(self, reading, top_k=3):
        return [
            {
                "feature": "power",
                "contribution": 1.0,
                "shap_value": 0.1,
                "direction": "high",
            }
        ]


class StubTuner:

    threshold = 1.0

    def observe(self, score):
        return None


# ---- Fix 2 ---------------------------------------------------------

def test_duplicate_reading_does_not_confirm_an_episode():

    d = EpisodeDetector(gap=timedelta(minutes=15), scale=1.0, min_flagged_readings=2)
    t = datetime(2026, 3, 1, tzinfo=UTC)

    assert d.accepts("s", t)

    d.process("s", t, 2.0, 1.0)

    assert not d.accepts("s", t)

    with pytest.raises(ValueError):
        d.process("s", t, 2.0, 1.0)

    assert d.flush() == []


def test_processor_skips_duplicate_reading():

    detector = EpisodeDetector(gap=3 * STEP, scale=1.0)
    writer = InMemoryWriter()
    processor = StreamProcessor(
        FakeModel(), StubTuner(), detector, writer, InMemoryPublisher()
    )

    reading = {"sensor_id": "s1", "timestamp": START_TIME}

    processor.handle(reading, score=0.0)
    processor.handle(reading, score=0.0)

    assert processor.skipped_stale == 1
    assert len(writer.rows) == 1


# ---- Fix 3 ---------------------------------------------------------

def test_replay_from_last_safe_commit_reproduces_the_same_episodes(stream_model):

    readings, _ = build_stream()
    X = np.array([[r[f] for f in FEATURES] for r in readings])
    scores = stream_model.score_batch(X)

    def new_processor():
        tuner = SignificanceThresholdTuner(
            stream_model.calibration_scores, percentile=97.0
        )
        detector = EpisodeDetector(
            gap=3 * STEP,
            scale=robust_scale(stream_model.calibration_scores),
            min_flagged_readings=2,
        )
        publisher = InMemoryPublisher()
        processor = StreamProcessor(
            stream_model, tuner, detector, InMemoryWriter(), publisher, use_tuner=False
        )
        return processor, publisher

    full, full_pub = new_processor()

    for r, s in zip(readings, scores):
        full.handle(r, score=float(s))

    full.finish()

    expected = {e["payload"]["episode_id"] for e in full_pub.events}

    first, first_pub = new_processor()
    crash_at = len(readings) // 2
    last_safe = -1

    for i in range(crash_at):
        first.handle(readings[i], score=float(scores[i]))

        if not first.detector.has_open_state():
            last_safe = i

    assert last_safe > 0
    # crash: no finish(), in-memory state lost

    second, second_pub = new_processor()

    for r, s in zip(readings[last_safe + 1:], scores[last_safe + 1:]):
        second.handle(r, score=float(s))

    second.finish()

    got = {
        e["payload"]["episode_id"] for e in first_pub.events + second_pub.events
    }

    assert got == expected


def _event(episode_id_start=0):

    t0 = START_TIME + episode_id_start * STEP

    return build_anomaly_event(
        sensor_id="s1",
        window_start=t0,
        window_end=t0 + STEP,
        first_flag_time=t0,
        confirmed_time=t0 + STEP,
        peak_time=t0,
        peak_score=1.0,
        threshold=0.5,
        n_flagged=2,
        closed_by="quiet",
        top_features=[
            {
                "feature": "power",
                "contribution": 1.0,
                "shap_value": 0.1,
                "direction": "high",
            }
        ],
        model_version="test",
    )


def test_eval_deduplicates_events_on_episode_id():

    episodes = [
        {
            "sensor_id": "s1",
            "kind": "a",
            "start_idx": 0,
            "end_idx": 2,
            "start_time": START_TIME,
            "end_time": START_TIME + 2 * STEP,
        }
    ]

    event = _event(0)

    once = evaluate_events([event], episodes, {"s1": 50})
    twice = evaluate_events([event, dict(event)], episodes, {"s1": 50})

    assert once["published_events"] == twice["published_events"] == 1
    assert once["event_precision"] == twice["event_precision"]


# ---- Fix 4 ---------------------------------------------------------

def test_explain_lists_only_features_pushing_toward_anomaly(stream_model):

    reading = {
        "sensor_id": "s",
        "timestamp": START_TIME,
        "temperature": 31.0,
        "humidity": 45.0,
        "door_open": 0,
        "power": 300.0,
    }

    top = stream_model.explain(reading)

    assert top[0]["feature"] == "temperature"
    assert top[0]["direction"] == "high"
    assert all(item["shap_value"] > 0 for item in top)
    assert "power" not in [item["feature"] for item in top]


def test_event_requires_shap_value():

    with pytest.raises(ValueError):
        build_anomaly_event(
            sensor_id="s1",
            window_start=START_TIME,
            window_end=START_TIME,
            first_flag_time=START_TIME,
            confirmed_time=START_TIME,
            peak_time=START_TIME,
            peak_score=1.0,
            threshold=0.5,
            n_flagged=1,
            closed_by="quiet",
            top_features=[
                {"feature": "power", "contribution": 1.0, "direction": "high"}
            ],
            model_version="test",
        )


# ---- Fix 5 ---------------------------------------------------------

def test_load_refuses_missing_and_mismatched_models(tmp_path, stream_model):

    with pytest.raises(FileNotFoundError):
        load_stream_model(tmp_path / "nope.joblib")

    path = save_stream_model(stream_model, tmp_path / "m.joblib")

    assert load_stream_model(path).version == MODEL_VERSION

    with pytest.raises(ValueError):
        load_stream_model(path, expected_version="stream-0.9")


def test_load_refuses_old_format_file(tmp_path, stream_model):

    path = tmp_path / "old.joblib"
    joblib.dump(stream_model, path)

    with pytest.raises(ValueError):
        load_stream_model(path)

def _new(model):
    tuner = SignificanceThresholdTuner(model.calibration_scores, percentile=97.0)
    det = EpisodeDetector(
        gap=3 * STEP,
        scale=robust_scale(model.calibration_scores),
        min_flagged_readings=2,
    )
    pub = InMemoryPublisher()
    proc = StreamProcessor(
        model, tuner, det, InMemoryWriter(), pub, use_tuner=False
    )
    return proc, pub


def _ids(events):
    return {e["payload"]["episode_id"] for e in events}


def _replay(model, readings, scores, crash_at, safe):
    first, first_pub = _new(model)
    last_safe = -1

    for i in range(crash_at + 1):
        first.handle(readings[i], score=float(scores[i]))
        if not first.detector.has_open_state():
            last_safe = i

    restart = last_safe + 1 if safe else crash_at + 1

    second, second_pub = _new(model)

    for r, s in zip(readings[restart:], scores[restart:]):
        second.handle(r, score=float(s))

    second.finish()

    return _ids(first_pub.events + second_pub.events)


def test_replay_matches_for_many_crash_points_and_naive_commit_does_not(stream_model):

    readings, _ = build_stream()
    X = np.array([[r[f] for f in FEATURES] for r in readings])
    scores = stream_model.score_batch(X)

    full, full_pub = _new(stream_model)
    open_idx = []

    for i, (r, s) in enumerate(zip(readings, scores)):
        full.handle(r, score=float(s))
        if full.detector.has_open_state():
            open_idx.append(i)

    full.finish()
    expected = _ids(full_pub.events)

    assert open_idx

    for crash_at in (800, 2000, 4000, 6500):
        assert _replay(stream_model, readings, scores, crash_at, True) == expected

    picks = open_idx[:: max(1, len(open_idx) // 4)][:4]

    assert any(
        _replay(stream_model, readings, scores, i, False) != expected
        for i in picks
    )