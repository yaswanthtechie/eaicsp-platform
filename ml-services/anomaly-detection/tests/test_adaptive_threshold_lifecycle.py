import numpy as np
import pytest

from src.adaptive_threshold import (
    AdaptiveThreshold,
    get_adaptive_threshold,
    reset_adaptive_thresholds,
)


# ============================================================
# Helpers
# ============================================================

def calibration_scores():
    return np.array(
        [
            0.10,
            0.11,
            0.12,
            0.13,
            0.14,
            0.15,
            0.16,
            0.17,
            0.18,
            0.19,
        ],
        dtype=float,
    )


# ============================================================
# 1. Calibration lifecycle
# ============================================================

def test_calibration_establishes_initial_threshold():
    manager = AdaptiveThreshold(
        window_size=5,
        percentile=90.0,
    )

    scores = calibration_scores()

    manager.initialize(
        scores
    )

    state = manager.get_state()

    assert state[
        "sample_count"
    ] == 5

    assert state[
        "adaptive_started"
    ] is False

    assert state[
        "initial_threshold"
    ] is not None

    assert state[
        "threshold"
    ] == pytest.approx(
        np.percentile(
            scores,
            90.0,
        )
    )


# ============================================================
# 2. Calibration threshold remains fixed
#    until trusted adaptation starts
# ============================================================

def test_calibration_threshold_remains_fixed_before_adaptation():
    manager = AdaptiveThreshold(
        window_size=5,
        percentile=90.0,
    )

    scores = calibration_scores()

    manager.initialize(
        scores
    )

    initial_threshold = (
        manager.get_threshold()
    )

    # Merely checking the threshold must
    # not start adaptive mode.
    for _ in range(10):

        assert (
            manager.get_threshold()
            == initial_threshold
        )

    state = manager.get_state()

    assert state[
        "adaptive_started"
    ] is False


# ============================================================
# 3. Trusted normal observation starts
#    adaptive lifecycle
# ============================================================

def test_trusted_update_starts_adaptive_lifecycle():
    manager = AdaptiveThreshold(
        window_size=5,
        percentile=90.0,
    )

    manager.initialize(
        calibration_scores()
    )

    assert (
        manager.get_state()[
            "adaptive_started"
        ]
        is False
    )

    manager.update(
        0.20
    )

    state = manager.get_state()

    assert state[
        "adaptive_started"
    ] is True

    assert state[
        "sample_count"
    ] == 5


# ============================================================
# 4. Adaptive threshold uses rolling
#    trusted observations
# ============================================================

def test_adaptive_lifecycle_uses_rolling_window():
    manager = AdaptiveThreshold(
        window_size=5,
        percentile=90.0,
    )

    manager.initialize(
        calibration_scores()
    )

    manager.update(
        0.20
    )

    expected = np.percentile(
        [
            0.15,
            0.16,
            0.17,
            0.18,
            0.19,
        ],
        90.0,
    )

    # The new trusted score replaces
    # the oldest retained calibration score.
    expected = np.percentile(
        [
            0.16,
            0.17,
            0.18,
            0.19,
            0.20,
        ],
        90.0,
    )

    assert manager.get_threshold() == (
        pytest.approx(expected)
    )


# ============================================================
# 5. Anomaly decision does not itself
#    start adaptation
# ============================================================

def test_anomaly_check_does_not_change_lifecycle():
    manager = AdaptiveThreshold(
        window_size=5,
        percentile=90.0,
    )

    manager.initialize(
        calibration_scores()
    )

    initial_threshold = (
        manager.get_threshold()
    )

    is_anomaly, threshold = (
        manager.is_anomaly(
            initial_threshold + 1.0
        )
    )

    assert is_anomaly is True

    assert threshold == (
        initial_threshold
    )

    state = manager.get_state()

    assert state[
        "adaptive_started"
    ] is False

    assert state[
        "threshold"
    ] == initial_threshold


# ============================================================
# 6. Anomalous observations must not
#    be inserted automatically
# ============================================================

def test_anomaly_decision_does_not_contaminate_baseline():
    manager = AdaptiveThreshold(
        window_size=5,
        percentile=90.0,
    )

    manager.initialize(
        calibration_scores()
    )

    initial_scores = list(
        manager.scores
    )

    threshold = (
        manager.get_threshold()
    )

    manager.is_anomaly(
        threshold + 100.0
    )

    assert list(
        manager.scores
    ) == initial_scores

    assert manager.get_state()[
        "adaptive_started"
    ] is False


# ============================================================
# 7. Trusted observations adapt,
#    anomalous observations do not
# ============================================================

def test_only_explicit_trusted_updates_change_baseline():
    manager = AdaptiveThreshold(
        window_size=5,
        percentile=90.0,
    )

    manager.initialize(
        calibration_scores()
    )

    original_scores = list(
        manager.scores
    )

    threshold = (
        manager.get_threshold()
    )

    # Detection does not modify baseline.
    manager.is_anomaly(
        threshold + 100.0
    )

    assert list(
        manager.scores
    ) == original_scores

    # Explicit trusted update does modify baseline.
    manager.update(
        0.20
    )

    assert list(
        manager.scores
    ) != original_scores

    assert manager.get_state()[
        "adaptive_started"
    ] is True


# ============================================================
# 8. Threshold remains available
#    throughout adaptation
# ============================================================

def test_threshold_remains_available_throughout_lifecycle():
    manager = AdaptiveThreshold(
        window_size=5,
        percentile=99.0,
    )

    manager.initialize(
        calibration_scores()
    )

    assert (
        manager.get_threshold()
        is not None
    )

    for score in [
        0.20,
        0.21,
        0.22,
        0.18,
        0.19,
        0.20,
        0.21,
    ]:

        manager.update(
            score
        )

        threshold = (
            manager.get_threshold()
        )

        assert threshold is not None

        assert np.isfinite(
            threshold
        )


# ============================================================
# 9. Reset terminates the lifecycle
# ============================================================

def test_reset_terminates_adaptive_lifecycle():
    manager = AdaptiveThreshold(
        window_size=5,
        percentile=90.0,
    )

    manager.initialize(
        calibration_scores()
    )

    manager.update(
        0.20
    )

    assert manager.get_state()[
        "adaptive_started"
    ] is True

    manager.reset()

    state = manager.get_state()

    assert state[
        "sample_count"
    ] == 0

    assert state[
        "threshold"
    ] is None

    assert state[
        "initial_threshold"
    ] is None

    assert state[
        "adaptive_started"
    ] is False


# ============================================================
# 10. Reinitialization starts a fresh
#     calibration lifecycle
# ============================================================

def test_reinitialize_starts_fresh_calibration_lifecycle():
    manager = AdaptiveThreshold(
        window_size=5,
        percentile=90.0,
    )

    first_scores = np.array(
        [
            0.10,
            0.11,
            0.12,
            0.13,
            0.14,
        ],
        dtype=float,
    )

    second_scores = np.array(
        [
            1.00,
            1.10,
            1.20,
            1.30,
            1.40,
        ],
        dtype=float,
    )

    manager.initialize(
        first_scores
    )

    manager.update(
        0.50
    )

    manager.initialize(
        second_scores
    )

    state = manager.get_state()

    assert state[
        "adaptive_started"
    ] is False

    assert state[
        "sample_count"
    ] == 5

    assert state[
        "initial_threshold"
    ] == pytest.approx(
        np.percentile(
            second_scores,
            90.0,
        )
    )

    assert manager.get_threshold() == (
        pytest.approx(
            np.percentile(
                second_scores,
                90.0,
            )
        )
    )


# ============================================================
# 11. Model-specific managers have
#     independent lifecycles
# ============================================================

def test_model_specific_threshold_managers_are_independent():
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

    scores = calibration_scores()

    iforest.initialize(
        scores
    )

    lof.initialize(
        scores
    )

    ocsvm.initialize(
        scores
    )

    iforest.update(
        10.0
    )

    assert iforest.get_state()[
        "adaptive_started"
    ] is True

    assert lof.get_state()[
        "adaptive_started"
    ] is False

    assert ocsvm.get_state()[
        "adaptive_started"
    ] is False


# ============================================================
# 12. Global reset restores all model
#     managers to initial lifecycle state
# ============================================================

def test_global_reset_restores_all_model_lifecycles():
    reset_adaptive_thresholds()

    scores = calibration_scores()

    managers = [
        get_adaptive_threshold(
            "iforest"
        ),
        get_adaptive_threshold(
            "lof"
        ),
        get_adaptive_threshold(
            "ocsvm"
        ),
    ]

    for manager in managers:

        manager.initialize(
            scores
        )

        manager.update(
            0.50
        )

        assert manager.get_state()[
            "adaptive_started"
        ] is True

    reset_adaptive_thresholds()

    for manager in managers:

        state = manager.get_state()

        assert state[
            "sample_count"
        ] == 0

        assert state[
            "threshold"
        ] is None

        assert state[
            "initial_threshold"
        ] is None

        assert state[
            "adaptive_started"
        ] is False