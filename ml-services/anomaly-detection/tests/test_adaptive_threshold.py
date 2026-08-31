import numpy as np
import pytest

from src.adaptive_threshold import (
    AdaptiveThreshold,
    get_adaptive_threshold,
    reset_adaptive_thresholds,
)


# ============================================================
# INITIALIZATION
# ============================================================

def test_initialization_calculates_calibration_threshold():
    """
    Initial threshold must be calculated from the complete
    calibration score population.

    The rolling window is only used for future adaptive updates.
    """

    scores = np.array(
        [
            0.10,
            0.20,
            0.30,
            0.40,
            0.50,
        ]
    )

    threshold = AdaptiveThreshold(
        window_size=3,
        percentile=80.0,
    )

    threshold.initialize(
        scores
    )

    expected = np.percentile(
        scores,
        80.0,
    )

    assert threshold.get_threshold() == pytest.approx(
        expected
    )


def test_initialization_keeps_only_recent_scores_for_future_updates():
    """
    Initialization calculates the threshold from all calibration
    scores, but only the most recent window_size observations are
    retained in the rolling adaptive baseline.
    """

    scores = np.array(
        [
            1.0,
            2.0,
            3.0,
            4.0,
            5.0,
        ]
    )

    threshold = AdaptiveThreshold(
        window_size=3,
        percentile=50.0,
    )

    threshold.initialize(
        scores
    )

    state = threshold.get_state()

    assert state["sample_count"] == 3

    assert state["window_size"] == 3

    assert state["adaptive_started"] is False

    assert state["initial_threshold"] == pytest.approx(
        np.percentile(
            scores,
            50.0,
        )
    )


def test_empty_initialization_has_no_threshold():
    """
    An empty calibration population cannot produce a threshold.
    """

    threshold = AdaptiveThreshold(
        window_size=5,
        percentile=99.0,
    )

    threshold.initialize(
        []
    )

    assert threshold.get_threshold() is None

    state = threshold.get_state()

    assert state["sample_count"] == 0

    assert state["threshold"] is None

    assert state["initial_threshold"] is None

    assert state["adaptive_started"] is False


# ============================================================
# ADAPTIVE UPDATE
# ============================================================

def test_update_starts_adaptive_mode():
    """
    The first trusted normal update transitions the manager from
    calibration mode into adaptive mode.
    """

    threshold = AdaptiveThreshold(
        window_size=5,
        percentile=90.0,
    )

    threshold.initialize(
        [
            1.0,
            2.0,
            3.0,
            4.0,
            5.0,
        ]
    )

    initial_threshold = (
        threshold.get_threshold()
    )

    threshold.update(
        10.0
    )

    state = threshold.get_state()

    assert state["adaptive_started"] is True

    assert state["sample_count"] == 5

    assert threshold.get_threshold() != pytest.approx(
        initial_threshold
    )


def test_update_recalculates_threshold_from_rolling_window():
    """
    Once adaptation starts, the threshold must be calculated from
    the current rolling trusted-score window.
    """

    threshold = AdaptiveThreshold(
        window_size=5,
        percentile=80.0,
    )

    threshold.initialize(
        [
            1.0,
            2.0,
            3.0,
            4.0,
            5.0,
        ]
    )

    threshold.update(
        10.0
    )

    expected_scores = np.array(
        [
            2.0,
            3.0,
            4.0,
            5.0,
            10.0,
        ]
    )

    expected_threshold = np.percentile(
        expected_scores,
        80.0,
    )

    assert threshold.get_threshold() == pytest.approx(
        expected_threshold
    )


def test_rolling_window_discards_oldest_score():
    """
    The rolling baseline must never exceed window_size.
    """

    threshold = AdaptiveThreshold(
        window_size=3,
        percentile=50.0,
    )

    threshold.initialize(
        [
            1.0,
            2.0,
            3.0,
        ]
    )

    threshold.update(
        4.0
    )

    state = threshold.get_state()

    assert state["sample_count"] == 3

    expected_scores = np.array(
        [
            2.0,
            3.0,
            4.0,
        ]
    )

    assert threshold.get_threshold() == pytest.approx(
        np.percentile(
            expected_scores,
            50.0,
        )
    )


def test_multiple_updates_keep_window_bounded():
    """
    Repeated trusted updates must continue to maintain the
    configured rolling window size.
    """

    threshold = AdaptiveThreshold(
        window_size=4,
        percentile=75.0,
    )

    threshold.initialize(
        [
            1.0,
            2.0,
            3.0,
            4.0,
        ]
    )

    for score in [
        5.0,
        6.0,
        7.0,
        8.0,
        9.0,
    ]:
        threshold.update(
            score
        )

    state = threshold.get_state()

    assert state["sample_count"] == 4

    expected_scores = np.array(
        [
            6.0,
            7.0,
            8.0,
            9.0,
        ]
    )

    expected_threshold = np.percentile(
        expected_scores,
        75.0,
    )

    assert threshold.get_threshold() == pytest.approx(
        expected_threshold
    )


# ============================================================
# ANOMALY CLASSIFICATION
# ============================================================

def test_score_below_threshold_is_normal():
    """
    Higher score means more anomalous.

    A score below the threshold must be classified as normal.
    """

    threshold = AdaptiveThreshold(
        window_size=5,
        percentile=90.0,
    )

    threshold.initialize(
        [
            1.0,
            2.0,
            3.0,
            4.0,
            5.0,
        ]
    )

    is_anomaly, active_threshold = (
        threshold.is_anomaly(
            1.0
        )
    )

    assert is_anomaly is False

    assert active_threshold == pytest.approx(
        threshold.get_threshold()
    )


def test_score_above_threshold_is_anomaly():
    """
    A score above the active threshold must be classified as
    anomalous.
    """

    threshold = AdaptiveThreshold(
        window_size=5,
        percentile=90.0,
    )

    threshold.initialize(
        [
            1.0,
            2.0,
            3.0,
            4.0,
            5.0,
        ]
    )

    is_anomaly, active_threshold = (
        threshold.is_anomaly(
            100.0
        )
    )

    assert is_anomaly is True

    assert active_threshold == pytest.approx(
        threshold.get_threshold()
    )


def test_score_equal_to_threshold_is_not_anomaly():
    """
    AdaptiveThreshold uses:

        score > threshold

    Therefore equality is not anomalous.
    """

    threshold = AdaptiveThreshold(
        window_size=5,
        percentile=90.0,
    )

    threshold.initialize(
        [
            1.0,
            2.0,
            3.0,
            4.0,
            5.0,
        ]
    )

    active_threshold = (
        threshold.get_threshold()
    )

    is_anomaly, returned_threshold = (
        threshold.is_anomaly(
            active_threshold
        )
    )

    assert is_anomaly is False

    assert returned_threshold == pytest.approx(
        active_threshold
    )


def test_anomaly_check_without_calibration_returns_false():
    """
    Without any baseline scores there is no threshold, so the
    manager cannot classify a score as anomalous.
    """

    threshold = AdaptiveThreshold(
        window_size=5,
        percentile=99.0,
    )

    is_anomaly, active_threshold = (
        threshold.is_anomaly(
            100.0
        )
    )

    assert is_anomaly is False

    assert active_threshold is None


# ============================================================
# PERCENTILE BEHAVIOR
# ============================================================

@pytest.mark.parametrize(
    "percentile",
    [
        90.0,
        95.0,
        99.0,
        99.5,
    ],
)
def test_configured_percentile_is_used(
    percentile,
):
    """
    The configured percentile must directly control the
    threshold calculation.
    """

    scores = np.array(
        [
            1.0,
            2.0,
            3.0,
            4.0,
            5.0,
            6.0,
            7.0,
            8.0,
            9.0,
            10.0,
        ]
    )

    threshold = AdaptiveThreshold(
        window_size=10,
        percentile=percentile,
    )

    threshold.initialize(
        scores
    )

    expected = np.percentile(
        scores,
        percentile,
    )

    assert threshold.get_threshold() == pytest.approx(
        expected
    )


def test_different_percentiles_produce_different_thresholds():
    """
    Higher percentiles should produce a threshold at least as high
    as lower percentiles for the same score distribution.
    """

    scores = np.array(
        [
            1.0,
            2.0,
            3.0,
            4.0,
            5.0,
            6.0,
            7.0,
            8.0,
            9.0,
            10.0,
        ]
    )

    low = AdaptiveThreshold(
        window_size=10,
        percentile=90.0,
    )

    high = AdaptiveThreshold(
        window_size=10,
        percentile=99.0,
    )

    low.initialize(
        scores
    )

    high.initialize(
        scores
    )

    assert high.get_threshold() >= (
        low.get_threshold()
    )


# ============================================================
# STATE
# ============================================================

def test_state_reports_calibration_mode_correctly():
    """
    get_state() must accurately describe the manager before
    adaptive updates begin.
    """

    threshold = AdaptiveThreshold(
        window_size=5,
        percentile=99.0,
    )

    threshold.initialize(
        [
            1.0,
            2.0,
            3.0,
        ]
    )

    state = threshold.get_state()

    assert state == {
        "sample_count": 3,
        "window_size": 5,
        "percentile": 99.0,
        "threshold": state["initial_threshold"],
        "initial_threshold": state[
            "initial_threshold"
        ],
        "adaptive_started": False,
    }


def test_state_reports_adaptive_mode_correctly():
    """
    get_state() must accurately describe the manager after trusted
    scores have started updating the rolling baseline.
    """

    threshold = AdaptiveThreshold(
        window_size=5,
        percentile=99.0,
    )

    threshold.initialize(
        [
            1.0,
            2.0,
            3.0,
        ]
    )

    threshold.update(
        4.0
    )

    state = threshold.get_state()

    assert state["sample_count"] == 4

    assert state["window_size"] == 5

    assert state["percentile"] == 99.0

    assert state["adaptive_started"] is True

    assert state["threshold"] == pytest.approx(
        threshold.get_threshold()
    )

    assert state["initial_threshold"] == pytest.approx(
        np.percentile(
            np.array(
                [
                    1.0,
                    2.0,
                    3.0,
                ]
            ),
            99.0,
        )
    )


# ============================================================
# RESET
# ============================================================

def test_reset_clears_adaptive_state():
    """
    reset() must remove both the rolling baseline and the
    calibration threshold.
    """

    threshold = AdaptiveThreshold(
        window_size=5,
        percentile=99.0,
    )

    threshold.initialize(
        [
            1.0,
            2.0,
            3.0,
            4.0,
            5.0,
        ]
    )

    threshold.update(
        10.0
    )

    threshold.reset()

    state = threshold.get_state()

    assert state["sample_count"] == 0

    assert state["threshold"] is None

    assert state["initial_threshold"] is None

    assert state["adaptive_started"] is False

    assert threshold.get_threshold() is None


def test_reset_allows_fresh_initialization():
    """
    After reset(), the same manager can be initialized again as a
    completely fresh threshold manager.
    """

    threshold = AdaptiveThreshold(
        window_size=5,
        percentile=99.0,
    )

    first_scores = np.array(
        [
            1.0,
            2.0,
            3.0,
        ]
    )

    second_scores = np.array(
        [
            10.0,
            20.0,
            30.0,
        ]
    )

    threshold.initialize(
        first_scores
    )

    threshold.update(
        100.0
    )

    threshold.reset()

    threshold.initialize(
        second_scores
    )

    expected = np.percentile(
        second_scores,
        99.0,
    )

    assert threshold.get_threshold() == pytest.approx(
        expected
    )

    state = threshold.get_state()

    assert state["sample_count"] == 3

    assert state["adaptive_started"] is False


# ============================================================
# MODEL-SPECIFIC MANAGERS
# ============================================================

def test_model_specific_managers_are_available():
    """
    The project-level managers must exist for all supported models.
    """

    expected_models = {
        "iforest",
        "lof",
        "ocsvm",
    }

    for model_name in expected_models:

        manager = get_adaptive_threshold(
            model_name
        )

        assert isinstance(
            manager,
            AdaptiveThreshold,
        )


@pytest.mark.parametrize(
    "model_name",
    [
        "iforest",
        "lof",
        "ocsvm",
    ],
)
def test_model_specific_managers_are_independent(
    model_name,
):
    """
    Updating one model manager must not modify another model's
    threshold manager.
    """

    reset_adaptive_thresholds()

    iforest = get_adaptive_threshold(
        "iforest"
    )

    lof = get_adaptive_threshold(
        "lof"
    )

    ocsvm = get_adaptive_threshold(
        "ocsvm"
    )

    managers = {
        "iforest": iforest,
        "lof": lof,
        "ocsvm": ocsvm,
    }

    selected = managers[
        model_name
    ]

    selected.initialize(
        [
            1.0,
            2.0,
            3.0,
            4.0,
            5.0,
        ]
    )

    selected.update(
        100.0
    )

    for other_name, other_manager in managers.items():

        if other_name == model_name:
            continue

        assert other_manager.get_threshold() is None


def test_unknown_model_raises_value_error():
    """
    Requesting a manager for an unsupported model must fail
    explicitly rather than silently creating one.
    """

    with pytest.raises(
        ValueError,
        match="Unknown model",
    ):
        get_adaptive_threshold(
            "unknown_model"
        )


# ============================================================
# GLOBAL RESET
# ============================================================

def test_reset_adaptive_thresholds_resets_all_models():
    """
    reset_adaptive_thresholds() must reset every model-specific
    manager.
    """

    for model_name in [
        "iforest",
        "lof",
        "ocsvm",
    ]:

        manager = get_adaptive_threshold(
            model_name
        )

        manager.initialize(
            [
                1.0,
                2.0,
                3.0,
            ]
        )

        manager.update(
            10.0
        )

    reset_adaptive_thresholds()

    for model_name in [
        "iforest",
        "lof",
        "ocsvm",
    ]:

        manager = get_adaptive_threshold(
            model_name
        )

        state = manager.get_state()

        assert state["sample_count"] == 0

        assert state["threshold"] is None

        assert state["initial_threshold"] is None

        assert state["adaptive_started"] is False