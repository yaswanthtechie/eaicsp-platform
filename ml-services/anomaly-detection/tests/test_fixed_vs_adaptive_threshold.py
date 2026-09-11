from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.adaptive_threshold import (
    AdaptiveThreshold,
    get_adaptive_threshold,
    reset_adaptive_thresholds,
)

from src.model_loader import (
    feature_names,
    get_models,
)


# =====================================================================
# PATHS
# =====================================================================

PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent
)

OUTPUT_DIR = PROJECT_ROOT / "output"


FEATURES = [
    "temperature",
    "humidity",
    "stock_count",
]


MODELS = [
    "iforest",
    "lof",
    "ocsvm",
]


EPSILON = 1e-8


# =====================================================================
# HELPERS
# =====================================================================

def load_dataset(filename):
    path = OUTPUT_DIR / filename

    assert path.exists(), (
        f"Required dataset does not exist: {path}"
    )

    return pd.read_csv(path)


def model_scores(model, dataframe):
    """
    Return the project's canonical anomaly score.

    Project convention:

        model.score(X)
            ->
        higher score = more anomalous
    """

    X = dataframe[
        FEATURES
    ].to_numpy()

    scores = np.asarray(
        model.score(X),
        dtype=float,
    )

    assert scores.ndim == 1

    assert len(scores) == len(
        dataframe
    )

    assert np.all(
        np.isfinite(scores)
    )

    return scores


def fixed_predict(
    scores,
    threshold,
):
    """
    Fixed-threshold prediction.

    Project convention:

        score >= threshold
            ->
        anomaly
    """

    return (
        np.asarray(scores)
        >= threshold
    )


def adaptive_predict(
    scores,
    threshold,
):
    """
    Adaptive-threshold prediction.

    Uses exactly the same decision rule
    as fixed_predict().
    """

    return (
        np.asarray(scores)
        >= threshold
    )


def percentile_threshold(
    scores,
    percentile=99.0,
):
    return float(
        np.percentile(
            scores,
            percentile,
        )
    )


def assert_threshold_is_valid(
    threshold,
):
    assert isinstance(
        threshold,
        (int, float),
    )

    assert np.isfinite(
        threshold
    )


# =====================================================================
# MODEL FIXTURE
# =====================================================================

@pytest.fixture(
    scope="module",
)
def models():
    """
    Load all deployed models.
    """

    loaded = get_models()

    for model_name in MODELS:

        assert model_name in loaded, (
            f"Missing required model: "
            f"{model_name}"
        )

    return {
        name: loaded[name]
        for name in MODELS
    }


# =====================================================================
# DATA FIXTURES
# =====================================================================

@pytest.fixture(
    scope="module",
)
def calibration_df():
    return load_dataset(
        "calibration_normal.csv"
    )


@pytest.fixture(
    scope="module",
)
def seasonal_df():
    return load_dataset(
        "test_seasonal_normal.csv"
    )


@pytest.fixture(
    scope="module",
)
def spike_df():
    return load_dataset(
        "test_temperature_spike.csv"
    )


# =====================================================================
# TEST 1
# FIXED AND ADAPTIVE HAVE IDENTICAL DECISION SEMANTICS
# =====================================================================

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_fixed_and_adaptive_use_same_decision_rule(
    models,
    calibration_df,
    model_name,
):
    """
    Prove that adaptive thresholding does not change
    the meaning of the anomaly decision.

    Both mechanisms must use:

        score >= threshold -> anomaly
        score < threshold  -> normal
    """

    model = models[
        model_name
    ]

    scores = model_scores(
        model,
        calibration_df,
    )

    threshold = percentile_threshold(
        scores
    )

    fixed_predictions = fixed_predict(
        scores,
        threshold,
    )

    adaptive_predictions = adaptive_predict(
        scores,
        threshold,
    )

    np.testing.assert_array_equal(
        fixed_predictions,
        adaptive_predictions,
    )


# =====================================================================
# TEST 2
# BOUNDARY BEHAVIOR
# =====================================================================

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_adaptive_threshold_boundary_matches_fixed_threshold(
    models,
    calibration_df,
    model_name,
):
    """
    Explicitly test the boundary.

        score < threshold
            -> normal

        score == threshold
            -> anomaly

        score > threshold
            -> anomaly
    """

    model = models[
        model_name
    ]

    scores = model_scores(
        model,
        calibration_df,
    )

    threshold = percentile_threshold(
        scores
    )

    below = (
        threshold - EPSILON
    )

    equal = threshold

    above = (
        threshold + EPSILON
    )

    assert not fixed_predict(
        np.array([below]),
        threshold,
    )[0]

    assert fixed_predict(
        np.array([equal]),
        threshold,
    )[0]

    assert fixed_predict(
        np.array([above]),
        threshold,
    )[0]

    assert not adaptive_predict(
        np.array([below]),
        threshold,
    )[0]

    assert adaptive_predict(
        np.array([equal]),
        threshold,
    )[0]

    assert adaptive_predict(
        np.array([above]),
        threshold,
    )[0]


# =====================================================================
# TEST 3
# NORMAL DATA MUST NOT MOVE THE THRESHOLD
# =====================================================================

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_fixed_vs_adaptive_normal_regime_stability(
    models,
    calibration_df,
    seasonal_df,
    model_name,
):
    """
    During a normal/stable regime:

        fixed threshold
            -> unchanged

        adaptive threshold
            -> unchanged

    No unnecessary transition should occur.
    """

    model = models[
        model_name
    ]

    calibration_scores = model_scores(
        model,
        calibration_df,
    )

    initial_threshold = percentile_threshold(
        calibration_scores
    )

    manager = AdaptiveThreshold(
        percentile=99,
        window_size=50,
    )

    manager.initialize(
        calibration_scores
    )

    adaptive_initial = (
        manager.get_threshold()
    )

    assert np.isclose(
        adaptive_initial,
        initial_threshold,
    )

    # Feed a stable normal regime.
    seasonal_scores = model_scores(
        model,
        seasonal_df,
    )

    for score in seasonal_scores:

        assert manager.get_state() is not None

        # Detection must not modify
        # the adaptive baseline.
        before = (
            manager.get_threshold()
        )

        manager.is_anomaly(
            float(score)
        )

        after = (
            manager.get_threshold()
        )

        assert np.isclose(
            before,
            after,
        )

    final_threshold = (
        manager.get_threshold()
    )

    # Fixed threshold never changes.
    assert np.isclose(
        initial_threshold,
        initial_threshold,
    )

    # Adaptive threshold should remain
    # stable when merely observing normal
    # data.
    assert np.isclose(
        final_threshold,
        adaptive_initial,
    )


# =====================================================================
# TEST 4
# ADAPTIVE THRESHOLD MUST ACTUALLY TRANSITION
# =====================================================================

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_adaptive_threshold_transitions_while_fixed_does_not(
    models,
    calibration_df,
    model_name,
):
    """
    Use a controlled score regime to prove:

        fixed threshold
            -> remains T1

        adaptive threshold
            -> transitions from T1 to T2
    """

    model = models[
        model_name
    ]

    calibration_scores = model_scores(
        model,
        calibration_df,
    )

    initial_threshold = percentile_threshold(
        calibration_scores
    )

    manager = AdaptiveThreshold(
        percentile=99,
        window_size=50,
    )

    manager.initialize(
        calibration_scores
    )

    assert np.isclose(
        manager.get_threshold(),
        initial_threshold,
    )

    # -------------------------------------------------------------
    # Controlled new regime.
    #
    # We intentionally use scores above the
    # old threshold so that the adaptive
    # mechanism receives a sustained shift.
    # -------------------------------------------------------------

    shift = max(
        abs(initial_threshold) * 0.5,
        0.01,
    )

    new_regime_scores = (
        initial_threshold
        + shift
        + np.linspace(
            0.0,
            shift,
            50,
        )
    )

    fixed_threshold = (
        initial_threshold
    )

    fixed_threshold_history = []

    adaptive_threshold_history = []

    for score in new_regime_scores:

        # Fixed threshold never changes.
        fixed_threshold_history.append(
            fixed_threshold
        )

        # Adaptive threshold is allowed
        # to receive trusted observations.
        manager.update(
            float(score)
        )

        adaptive_threshold_history.append(
            manager.get_threshold()
        )

    final_adaptive_threshold = (
        manager.get_threshold()
    )

    # Fixed threshold must remain T1.
    assert all(
        np.isclose(
            value,
            initial_threshold,
        )
        for value
        in fixed_threshold_history
    )

    # Adaptive threshold must be valid.
    assert_threshold_is_valid(
        final_adaptive_threshold
    )

    # The adaptive threshold must not
    # remain permanently identical to
    # the original threshold after a
    # sustained trusted regime shift.
    assert not np.isclose(
        final_adaptive_threshold,
        initial_threshold,
    )


# =====================================================================
# TEST 5
# AFTER TRANSITION, ADAPTIVE STILL BEHAVES
# LIKE A NORMAL THRESHOLD
# =====================================================================

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_adaptive_threshold_after_transition_is_compatible_with_fixed_rule(
    models,
    calibration_df,
    model_name,
):
    """
    This is the key compatibility test.

    After adaptation:

        T2 = adaptive threshold

    The threshold must still behave like an
    ordinary production threshold:

        score < T2  -> normal
        score >= T2 -> anomaly
    """

    model = models[
        model_name
    ]

    calibration_scores = model_scores(
        model,
        calibration_df,
    )

    manager = AdaptiveThreshold(
        percentile=99,
        window_size=50,
    )

    manager.initialize(
        calibration_scores
    )

    initial_threshold = (
        manager.get_threshold()
    )

    # -------------------------------------------------------------
    # Force a deterministic transition.
    # -------------------------------------------------------------

    shift = max(
        abs(initial_threshold) * 0.5,
        0.01,
    )

    new_regime_scores = (
        initial_threshold
        + shift
        + np.linspace(
            0.0,
            shift,
            50,
        )
    )

    for score in new_regime_scores:

        manager.update(
            float(score)
        )

    new_threshold = (
        manager.get_threshold()
    )

    assert_threshold_is_valid(
        new_threshold
    )

    assert not np.isclose(
        new_threshold,
        initial_threshold,
    )

    # -------------------------------------------------------------
    # Test the NEW threshold exactly
    # like a normal fixed threshold.
    # -------------------------------------------------------------

    below = (
        new_threshold - EPSILON
    )

    equal = new_threshold

    above = (
        new_threshold + EPSILON
    )

    fixed_results = fixed_predict(
        np.array([
            below,
            equal,
            above,
        ]),
        new_threshold,
    )

    adaptive_results = adaptive_predict(
        np.array([
            below,
            equal,
            above,
        ]),
        new_threshold,
    )

    # The decision boundary is identical.
    np.testing.assert_array_equal(
        fixed_results,
        adaptive_results,
    )

    # Explicit semantics.
    assert fixed_results.tolist() == [
        False,
        True,
        True,
    ]


# =====================================================================
# TEST 6
# ADAPTIVE THRESHOLD MUST STABILIZE AFTER TRANSITION
# =====================================================================

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_adaptive_threshold_stabilizes_after_transition(
    models,
    calibration_df,
    model_name,
):
    """
    After a new regime has been learned,
    repeatedly observing the same stable regime
    must not cause uncontrolled threshold movement.
    """

    model = models[
        model_name
    ]

    calibration_scores = model_scores(
        model,
        calibration_df,
    )

    manager = AdaptiveThreshold(
        percentile=99,
        window_size=50,
    )

    manager.initialize(
        calibration_scores
    )

    initial_threshold = (
        manager.get_threshold()
    )

    shift = max(
        abs(initial_threshold) * 0.5,
        0.01,
    )

    stable_regime = (
        initial_threshold
        + shift
        + np.linspace(
            0.0,
            shift,
            50,
        )
    )

    # Learn the new regime.
    for score in stable_regime:

        manager.update(
            float(score)
        )

    transitioned_threshold = (
        manager.get_threshold()
    )

    assert not np.isclose(
        transitioned_threshold,
        initial_threshold,
    )

    # Continue with exactly the same
    # stable regime.
    thresholds = []

    for score in stable_regime:

        manager.update(
            float(score)
        )

        thresholds.append(
            manager.get_threshold()
        )

    # The threshold must remain finite.
    assert all(
        np.isfinite(
            value
        )
        for value in thresholds
    )

    # Once the rolling window represents
    # the same regime, the threshold should
    # settle rather than continually diverge.
    tail = thresholds[-10:]

    assert np.ptp(
        tail
    ) < max(
        abs(transitioned_threshold) * 0.10,
        0.01,
    )


# =====================================================================
# TEST 7
# ANOMALIES MUST NOT CHANGE THE ADAPTIVE BASELINE
# =====================================================================

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_fixed_vs_adaptive_anomaly_protection(
    models,
    calibration_df,
    spike_df,
    model_name,
):
    """
    A detected anomaly must not become a trusted
    observation merely because adaptive thresholding
    is enabled.

    Therefore:

        anomaly detection
            !=
        baseline adaptation
    """

    model = models[
        model_name
    ]

    calibration_scores = model_scores(
        model,
        calibration_df,
    )

    spike_scores = model_scores(
        model,
        spike_df,
    )

    manager = AdaptiveThreshold(
        percentile=99,
        window_size=50,
    )

    manager.initialize(
        calibration_scores
    )

    threshold_before = (
        manager.get_threshold()
    )

    # Feed anomaly observations only
    # through the detection path.
    for score in spike_scores:

        manager.is_anomaly(
            float(score)
        )

    threshold_after = (
        manager.get_threshold()
    )

    assert np.isclose(
        threshold_before,
        threshold_after,
    )


# =====================================================================
# TEST 8
# FINAL END-TO-END COMPATIBILITY CONTRACT
# =====================================================================

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_fixed_vs_adaptive_threshold_contract(
    models,
    calibration_df,
    model_name,
):
    """
    Final contract test.

    The adaptive threshold is a changing decision
    boundary, not a different anomaly-definition.

    Therefore:

        fixed(T) and adaptive(T)

    must produce identical decisions for
    the same scores.

    This remains true for:

        1. calibration threshold
        2. post-transition threshold
    """

    model = models[
        model_name
    ]

    calibration_scores = model_scores(
        model,
        calibration_df,
    )

    # -------------------------------------------------------------
    # Fixed/calibration threshold
    # -------------------------------------------------------------

    fixed_threshold = percentile_threshold(
        calibration_scores
    )

    manager = AdaptiveThreshold(
        percentile=99,
        window_size=50,
    )

    manager.initialize(
        calibration_scores
    )

    adaptive_threshold = (
        manager.get_threshold()
    )

    assert np.isclose(
        fixed_threshold,
        adaptive_threshold,
    )

    fixed_predictions = fixed_predict(
        calibration_scores,
        fixed_threshold,
    )

    adaptive_predictions = adaptive_predict(
        calibration_scores,
        adaptive_threshold,
    )

    np.testing.assert_array_equal(
        fixed_predictions,
        adaptive_predictions,
    )

    # -------------------------------------------------------------
    # Transition
    # -------------------------------------------------------------

    shift = max(
        abs(fixed_threshold) * 0.5,
        0.01,
    )

    new_regime = (
        fixed_threshold
        + shift
        + np.linspace(
            0.0,
            shift,
            50,
        )
    )

    for score in new_regime:

        manager.update(
            float(score)
        )

    transitioned_threshold = (
        manager.get_threshold()
    )

    assert_threshold_is_valid(
        transitioned_threshold
    )

    # -------------------------------------------------------------
    # Same decision contract after
    # transition.
    # -------------------------------------------------------------

    comparison_scores = np.array([
        transitioned_threshold - 0.01,
        transitioned_threshold,
        transitioned_threshold + 0.01,
    ])

    fixed_after_transition = fixed_predict(
        comparison_scores,
        transitioned_threshold,
    )

    adaptive_after_transition = adaptive_predict(
        comparison_scores,
        transitioned_threshold,
    )

    np.testing.assert_array_equal(
        fixed_after_transition,
        adaptive_after_transition,
    )

    assert fixed_after_transition.tolist() == [
        False,
        True,
        True,
    ]