from datetime import UTC, datetime, timedelta

import pytest

from src.episode_detector import EpisodeDetector
from src.stream_processor import (
    InMemoryPublisher,
    InMemoryWriter,
    StreamProcessor,
)


T0 = datetime(2026, 1, 1, tzinfo=UTC)
STEP = timedelta(minutes=5)
GAP = 3 * STEP

NORMAL = 0.0
FLAG = 1.5


class FakeModel:

    version = "fake"

    def score_one(self, reading):
        return reading["score"]

    def explain(self, reading, top_k=3):
        return [{"feature": "temperature", "contribution": 1.0, "direction": "high"}]


class StubTuner:

    def __init__(self, threshold=1.0):
        self.threshold = threshold
        self.observed = []

    def observe(self, score):
        self.observed.append(score)
        return None


def reading(i, score, sensor="s1"):
    return {"sensor_id": sensor, "timestamp": T0 + i * STEP, "score": score}


def make(use_tuner=True, min_flagged=2):

    tuner = StubTuner()
    writer = InMemoryWriter()
    publisher = InMemoryPublisher()
    detector = EpisodeDetector(
        gap=GAP, scale=1.0, min_flagged_readings=min_flagged, severe_margin=3.0
    )

    proc = StreamProcessor(FakeModel(), tuner, detector, writer, publisher, use_tuner)

    return proc, tuner, writer, publisher


def run(proc, scores, sensor="s1"):

    out = []

    for i, score in enumerate(scores):
        out.extend(proc.handle(reading(i, score, sensor)))

    return out


def test_every_reading_is_written():

    proc, _, writer, _ = make()
    run(proc, [NORMAL, FLAG, FLAG, NORMAL])

    assert len(writer.rows) == 4
    assert [row[2] for row in writer.rows] == [False, True, True, False]


def test_one_event_per_episode_with_explanation():

    proc, _, _, publisher = make()
    run(proc, [FLAG] * 8 + [NORMAL] * 5)

    assert len(publisher.events) == 1

    payload = publisher.events[0]["payload"]

    assert payload["n_flagged"] == 8
    assert payload["top_features"][0]["feature"] == "temperature"
    assert payload["model_version"] == "fake"


def test_tuner_only_fed_by_quiet_normal_readings():

    proc, tuner, _, _ = make()
    run(proc, [NORMAL, NORMAL, FLAG, FLAG, NORMAL, NORMAL, NORMAL, NORMAL, NORMAL])

    assert tuner.observed == [0.0, 0.0, 0.0, 0.0]


def test_frozen_run_never_feeds_tuner():

    proc, tuner, _, _ = make(use_tuner=False)
    run(proc, [NORMAL] * 10)

    assert tuner.observed == []


def test_finish_flushes_open_episode():

    proc, _, _, publisher = make()
    run(proc, [FLAG, FLAG, FLAG])

    events = proc.finish()

    assert len(events) == 1
    assert publisher.events[0]["payload"]["closed_by"] == "shutdown"


def test_severe_single_reading_publishes():

    proc, _, _, publisher = make()
    run(proc, [10.0] + [NORMAL] * 5)

    assert len(publisher.events) == 1
    assert publisher.events[0]["payload"]["severe"] is True


def test_publisher_failure_propagates():

    class Broken:
        def publish(self, event):
            raise RuntimeError("down")

    detector = EpisodeDetector(gap=GAP, scale=1.0)
    proc = StreamProcessor(FakeModel(), StubTuner(), detector, InMemoryWriter(), Broken())

    with pytest.raises(RuntimeError):
        run(proc, [FLAG, FLAG] + [NORMAL] * 5)