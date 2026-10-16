from datetime import UTC, datetime, timedelta

import pytest

from src.episode_detector import EpisodeDetector
from src.stream_events import build_anomaly_event


T0 = datetime(2026, 1, 1, tzinfo=UTC)
STEP = timedelta(minutes=5)
GAP = 3 * STEP

NORMAL = 0.0
FLAG = 1.5      # >= threshold 1.0, below the severe level (4.0)
SEVERE = 10.0


def make(**overrides):

    params = dict(gap=GAP, scale=1.0, min_flagged_readings=2, severe_margin=3.0)
    params.update(overrides)

    return EpisodeDetector(**params)


def feed(detector, scores, sensor="s1", threshold=1.0):
    """Feed scores at 5-minute steps. Return [(index, episode), ...]."""

    out = []

    for i, score in enumerate(scores):

        episode = detector.process(
            sensor, T0 + i * STEP, score, threshold, reading={"i": i}
        )

        if episode is not None:
            out.append((i, episode))

    return out


def test_two_flags_make_one_episode():

    det = make()
    out = feed(det, [FLAG, FLAG, NORMAL, NORMAL, NORMAL, NORMAL])

    assert len(out) == 1

    index, ep = out[0]

    assert index == 5                      # closed by the first reading after the gap
    assert ep["window_start"] == T0
    assert ep["window_end"] == T0 + STEP
    assert ep["n_flagged"] == 2
    assert ep["confirmed_time"] == T0 + STEP
    assert ep["closed_by"] == "quiet"
    assert ep["severe"] is False


def test_long_episode_gives_exactly_one_event():

    det = make()
    out = feed(det, [FLAG] * 10 + [NORMAL] * 5)

    assert len(out) == 1
    assert out[0][1]["n_flagged"] == 10
    assert det.episodes_emitted == 1


def test_single_mild_flag_is_dropped_and_counted():

    det = make()
    out = feed(det, [FLAG, NORMAL, NORMAL, NORMAL, NORMAL])

    assert out == []
    assert det.dropped_candidates == 1
    assert det.episodes_emitted == 0


def test_min_one_keeps_single_flag():

    det = make(min_flagged_readings=1)
    out = feed(det, [FLAG, NORMAL, NORMAL, NORMAL, NORMAL])

    assert len(out) == 1
    assert out[0][1]["n_flagged"] == 1
    assert det.dropped_candidates == 0


def test_single_severe_reading_opens_episode():

    det = make()
    out = feed(det, [SEVERE, NORMAL, NORMAL, NORMAL, NORMAL])

    assert len(out) == 1

    ep = out[0][1]

    assert ep["n_flagged"] == 1
    assert ep["severe"] is True
    assert ep["confirmed_time"] == T0
    assert det.dropped_candidates == 0


def test_severe_level_follows_the_current_threshold():

    det = make()

    # threshold 1.0 -> severe level 4.0, so 3.5 is a mild flag.
    det.process("s1", T0, 3.5, 1.0)
    assert det.flush() == []

    # threshold 0.4 -> severe level 3.4, so 3.5 is severe.
    det.process("s2", T0, 3.5, 0.4)
    episodes = det.flush()

    assert len(episodes) == 1
    assert episodes[0]["severe"] is True


def test_flags_exactly_one_gap_apart_join():

    det = make()
    # flags at index 0, 3, 6: each exactly 15 minutes apart.
    out = feed(det, [FLAG, NORMAL, NORMAL, FLAG, NORMAL, NORMAL, FLAG] + [NORMAL] * 4)

    assert len(out) == 1
    assert out[0][1]["n_flagged"] == 3
    assert out[0][1]["window_end"] == T0 + 6 * STEP


def test_flags_more_than_one_gap_apart_split():

    det = make(min_flagged_readings=1)
    out = feed(det, [FLAG, NORMAL, NORMAL, NORMAL, FLAG] + [NORMAL] * 4)

    assert len(out) == 2
    assert out[0][1]["window_start"] == T0
    assert out[1][1]["window_start"] == T0 + 4 * STEP


def test_scattered_false_flags_do_not_chain_into_an_episode():

    det = make()
    # lone flags 5 readings apart, none severe
    out = feed(det, ([FLAG] + [NORMAL] * 4) * 4 + [NORMAL] * 4)

    assert out == []
    assert det.dropped_candidates == 4


def test_peak_reading_is_tracked():

    det = make()
    out = feed(det, [FLAG, 3.0, 2.0, NORMAL, NORMAL, NORMAL, NORMAL])

    ep = out[0][1]

    assert ep["peak_score"] == 3.0
    assert ep["peak_time"] == T0 + STEP
    assert ep["peak_reading"] == {"i": 1}
    assert ep["threshold"] == 1.0


def test_sensors_are_independent():

    det = make()

    det.process("s1", T0, FLAG, 1.0)
    det.process("s2", T0, NORMAL, 1.0)
    det.process("s1", T0 + STEP, FLAG, 1.0)

    assert det.is_active("s1")
    assert not det.is_active("s2")

    episodes = det.flush()

    assert [e["sensor_id"] for e in episodes] == ["s1"]


def test_is_active_lifecycle():

    det = make()

    assert not det.is_active("s1")

    det.process("s1", T0, FLAG, 1.0)
    assert det.is_active("s1")

    feed_after = [NORMAL] * 4

    for i, score in enumerate(feed_after, start=1):
        det.process("s1", T0 + i * STEP, score, 1.0)

    assert not det.is_active("s1")


def test_flush_emits_open_episode_as_shutdown():

    det = make()
    feed(det, [FLAG, FLAG, FLAG])

    episodes = det.flush()

    assert len(episodes) == 1
    assert episodes[0]["closed_by"] == "shutdown"
    assert episodes[0]["n_flagged"] == 3
    assert det.flush() == []


def test_flush_drops_unconfirmed_candidate():

    det = make()
    feed(det, [FLAG])

    assert det.flush() == []
    assert det.dropped_candidates == 1


def test_out_of_order_reading_raises():

    det = make()
    det.process("s1", T0 + STEP, NORMAL, 1.0)

    with pytest.raises(ValueError):
        det.process("s1", T0, NORMAL, 1.0)


def test_non_finite_score_raises():

    with pytest.raises(ValueError):
        make().process("s1", T0, float("nan"), 1.0)


@pytest.mark.parametrize(
    "overrides",
    [
        {"gap": 15},
        {"gap": timedelta(0)},
        {"scale": 0},
        {"scale": float("inf")},
        {"min_flagged_readings": 0},
        {"min_flagged_readings": True},
        {"severe_margin": -1},
    ],
)
def test_invalid_parameters_are_rejected(overrides):

    with pytest.raises(ValueError):
        make(**overrides)


def test_episode_output_fits_the_event_builder():

    det = make()
    ep = feed(det, [FLAG, FLAG] + [NORMAL] * 4)[0][1]

    ep = dict(ep)
    ep.pop("peak_reading")

    event = build_anomaly_event(
        **ep,
        top_features=[
            {"feature": "temperature", "contribution": 1.0, "shap_value": 0.1, "direction": "high"}
        ],
        model_version="test",
    )

    assert event["payload"]["sensor_id"] == "s1"
    assert event["payload"]["n_flagged"] == 2