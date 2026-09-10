import numpy as np
import pytest

from src.adaptive_threshold import (
    AdaptiveThreshold,
)


# ============================================================
# HELPERS
# ============================================================

def create_threshold():
    """
    Create a fresh AdaptiveThreshold for each integration test.

    Production configuration:

        window_size = 50
        percentile = 99.0
    """

    return AdaptiveThreshold(
        window_size=50,
        percentile=99.0,
    )


def assert_finite_scores(scores):
    """
    Ensure the model produced usable anomaly scores.
    """

    scores = np.asarray(
        scores,
        dtype=float,
    )

    assert scores.size > 0

    assert np.all(
        np.isfinite(scores)
    )

    return scores


# ============================================================
# CALIBRATION
# ============================================================

def test_real_model_scores_produce_initial_threshold(
    model_name,
    model_calibration_scores,
):
    """
    Verify that every supported model can produce a usable
    initial threshold from real calibration scores.

    Flow:

        real calibration scores
                ↓
        AdaptiveThreshold.initialize()
                ↓
        99th percentile threshold
    """

    scores = assert_finite_scores(
        model_calibration_scores
    )

    threshold = create_threshold()

    threshold.initialize(
        scores
    )

    active_threshold = (
        threshold.get_threshold()
    )

    expected_threshold = np.percentile(
        scores,
        99.0,
    )

    assert active_threshold is not None

    assert np.isfinite(
        active_threshold
    )

    assert active_threshold == pytest.approx(
        expected_threshold
    )

    state = threshold.get_state()

    assert state[
        "sample_count"
    ] == min(
        50,
        len(scores),
    )

    assert state[
        "adaptive_started"
    ] is False

    assert state[
        "initial_threshold"
    ] == pytest.approx(
        expected_threshold
    )


# ============================================================
# CALIBRATION → ADAPTATION
# ============================================================

def test_real_model_scores_can_start_adaptation(
    model_name,
    model_calibration_scores,
):
    """
    Verify that trusted real scores transition the threshold
    manager from calibration mode to adaptive mode.

    The manager starts with the most recent 50 calibration
    scores.

    Ten new trusted scores are then added.

    Therefore the rolling window becomes:

        last 40 calibration scores
        +
        10 newly trusted scores

        = 50 scores

    The adaptive threshold must equal the 99th percentile
    of that actual rolling window.
    """

    scores = assert_finite_scores(
        model_calibration_scores
    )

    threshold = create_threshold()

    threshold.initialize(
        scores
    )

    initial_threshold = (
        threshold.get_threshold()
    )

    assert initial_threshold is not None

    # Use the final ten real scores as trusted adaptive
    # observations.
    update_scores = scores[
        -10:
    ]

    for score in update_scores:

        threshold.update(
            score
        )

    state = threshold.get_state()

    assert state[
        "adaptive_started"
    ] is True

    assert state[
        "sample_count"
    ] == min(
        50,
        len(scores),
    )

    adaptive_threshold = (
        threshold.get_threshold()
    )

    assert adaptive_threshold is not None

    assert np.isfinite(
        adaptive_threshold
    )

    # --------------------------------------------------------
    # Reconstruct the actual rolling window.
    #
    # initialize() retained the last 50 calibration scores.
    # Ten updates replace the oldest ten observations.
    # --------------------------------------------------------

    window_size = state[
        "window_size"
    ]

    percentile = state[
        "percentile"
    ]

    update_count = len(
        update_scores
    )

    remaining_calibration = max(
        0,
        window_size - update_count,
    )

    expected_scores = np.concatenate(
        [
            scores[
                -remaining_calibration:
            ],
            update_scores,
        ]
    )

    # When there are fewer than 50 total calibration scores,
    # the manager cannot contain more observations than exist.
    expected_scores = expected_scores[
        -window_size:
    ]

    expected_threshold = np.percentile(
        expected_scores,
        percentile,
    )

    assert adaptive_threshold == pytest.approx(
        expected_threshold
    )


# ============================================================
# ROLLING WINDOW
# ============================================================

def test_real_model_scores_respect_rolling_window(
    model_name,
    model_calibration_scores,
):
    """
    Verify that the adaptive baseline remains bounded by
    window_size while processing real model scores.
    """

    scores = assert_finite_scores(
        model_calibration_scores
    )

    threshold = create_threshold()

    threshold.initialize(
        scores
    )

    for score in scores:

        threshold.update(
            score
        )

    state = threshold.get_state()

    assert state[
        "sample_count"
    ] == min(
        50,
        len(scores),
    )

    assert state[
        "sample_count"
    ] <= 50

    expected_scores = scores[
        -50:
    ]

    expected_threshold = np.percentile(
        expected_scores,
        99.0,
    )

    assert threshold.get_threshold() == pytest.approx(
        expected_threshold
    )


# ============================================================
# REAL SCORE CLASSIFICATION
# ============================================================

def test_real_calibration_scores_are_mostly_below_threshold(
    model_name,
    model_calibration_scores,
):
    """
    A 99th-percentile calibration threshold should leave the
    vast majority of calibration scores at or below threshold.
    """

    scores = assert_finite_scores(
        model_calibration_scores
    )

    threshold = create_threshold()

    threshold.initialize(
        scores
    )

    active_threshold = (
        threshold.get_threshold()
    )

    assert active_threshold is not None

    normal_count = np.sum(
        scores
        <= active_threshold
    )

    normal_fraction = (
        normal_count
        / len(scores)
    )

    assert normal_fraction >= 0.98, (
        f"{model_name}: only "
        f"{normal_fraction:.3%} of calibration "
        "scores were at or below the 99th-percentile "
        "threshold."
    )


def test_real_calibration_scores_above_threshold_are_anomalies(
    model_name,
    model_calibration_scores,
):
    """
    Scores above the active threshold must be classified
    as anomalies.
    """

    scores = assert_finite_scores(
        model_calibration_scores
    )

    threshold = create_threshold()

    threshold.initialize(
        scores
    )

    active_threshold = (
        threshold.get_threshold()
    )

    assert active_threshold is not None

    high_scores = scores[
        scores > active_threshold
    ]

    if high_scores.size == 0:

        pytest.skip(
            f"{model_name}: calibration dataset contains "
            "no score above its 99th-percentile threshold."
        )

    for score in high_scores:

        is_anomaly, returned_threshold = (
            threshold.is_anomaly(
                score
            )
        )

        assert is_anomaly is True

        assert returned_threshold == pytest.approx(
            active_threshold
        )


# ============================================================
# MODEL INDEPENDENCE
# ============================================================

def test_all_models_produce_independent_thresholds(
    all_calibration_scores,
):
    """
    Each model must maintain its own threshold calculation.

    Numerical threshold values are not expected to be equal
    because the models produce different score distributions.
    """

    thresholds = {}

    for model_name, scores in (
        all_calibration_scores.items()
    ):

        scores = assert_finite_scores(
            scores
        )

        threshold = create_threshold()

        threshold.initialize(
            scores
        )

        active_threshold = (
            threshold.get_threshold()
        )

        assert active_threshold is not None

        assert np.isfinite(
            active_threshold
        )

        thresholds[
            model_name
        ] = active_threshold

    assert set(
        thresholds.keys()
    ) == {
        "iforest",
        "lof",
        "ocsvm",
    }

    for value in thresholds.values():

        assert np.isfinite(
            value
        )


# ============================================================
# ADAPTIVE WINDOW TRACKING
# ============================================================

def test_adaptive_threshold_tracks_recent_real_scores(
    model_name,
    model_calibration_scores,
):
    """
    After adaptation begins, the threshold must correspond
    to the most recent window_size trusted model scores.
    """

    scores = assert_finite_scores(
        model_calibration_scores
    )

    if len(scores) < 50:

        pytest.skip(
            f"{model_name}: fewer than 50 calibration scores."
        )

    threshold = create_threshold()

    threshold.initialize(
        scores
    )

    for score in scores:

        threshold.update(
            score
        )

    state = threshold.get_state()

    assert state[
        "adaptive_started"
    ] is True

    assert state[
        "sample_count"
    ] == 50

    recent_scores = scores[
        -50:
    ]

    expected_threshold = np.percentile(
        recent_scores,
        99.0,
    )

    assert threshold.get_threshold() == pytest.approx(
        expected_threshold
    )


# ============================================================
# THRESHOLD AVAILABILITY
# ============================================================

def test_real_score_stream_never_loses_threshold(
    model_name,
    model_calibration_scores,
):
    """
    Once calibrated, processing finite real model scores
    must never leave the threshold undefined.
    """

    scores = assert_finite_scores(
        model_calibration_scores
    )

    threshold = create_threshold()

    threshold.initialize(
        scores
    )

    assert (
        threshold.get_threshold()
        is not None
    )

    for score in scores:

        threshold.update(
            score
        )

        active_threshold = (
            threshold.get_threshold()
        )

        assert active_threshold is not None

        assert np.isfinite(
            active_threshold
        )