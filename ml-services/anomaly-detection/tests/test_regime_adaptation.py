import numpy as np
import pandas as pd
import pytest

from src.model_loader import (
    feature_names,
    get_models,
)

from src.regime_detector import (
    RegimeDetector,
)


CALIBRATION = "output/calibration_normal.csv"
SEASONAL = "output/test_seasonal_normal.csv"
DRIFT = "output/test_temperature_drift.csv"


MODELS = [
    "iforest",
    "lof",
    "ocsvm",
]


def get_scores(
    df,
    model,
):
    """
    Convert model output into the project's anomaly-score
    convention.

    Higher score = more anomalous.
    """

    X = df[
        feature_names
    ].to_numpy()

    return -model.score(X)


def feed_scores(
    detector,
    scores,
):
    """
    Feed scores sequentially into the regime detector.
    """

    results = []

    for score in scores:

        result = detector.observe(
            score
        )

        results.append(result)

    return results


@pytest.fixture
def datasets():
    calibration = pd.read_csv(
        CALIBRATION
    )

    seasonal = pd.read_csv(
        SEASONAL
    )

    drift = pd.read_csv(
        DRIFT
    )

    return (
        calibration,
        seasonal,
        drift,
    )


def create_detector(
    calibration_scores,
):
    """
    Create and initialize a detector using the known
    calibration-normal regime.
    """

    detector = RegimeDetector(
        candidate_sizes=[
            10,
            25,
            50,
            100,
            200,
        ],
        baseline_size=100,
        shift_sigma=2.0,
        stability_tolerance=0.20,
        min_stable_blocks=2,
    )

    detector.initialize(
        calibration_scores
    )

    return detector


# ------------------------------------------------------------
# Test 1
# Original calibration data should not trigger a new regime.
# ------------------------------------------------------------

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_original_normal_does_not_trigger_regime(
    datasets,
    model_name,
):

    calibration_df, _, _ = datasets

    model = get_models()[
        model_name
    ]

    calibration_scores = get_scores(
        calibration_df,
        model,
    )

    detector = create_detector(
        calibration_scores
    )

    results = feed_scores(
        detector,
        calibration_scores,
    )

    assert not detector.is_confirmed()

    assert not any(
        result["regime_confirmed"]
        for result in results
    )


# ------------------------------------------------------------
# Test 2
# Stable seasonal regime should eventually be detected.
# ------------------------------------------------------------

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_stable_seasonal_shift_is_detected(
    datasets,
    model_name,
):

    calibration_df, seasonal_df, _ = datasets

    model = get_models()[
        model_name
    ]

    calibration_scores = get_scores(
        calibration_df,
        model,
    )

    seasonal_scores = get_scores(
        seasonal_df,
        model,
    )

    detector = create_detector(
        calibration_scores
    )

    results = feed_scores(
        detector,
        seasonal_scores,
    )

    confirmed = any(
        result["regime_confirmed"]
        for result in results
    )

    assert confirmed

    assert detector.is_confirmed()

    confirmed_scores = (
        detector.get_confirmed_scores()
    )

    assert len(
        confirmed_scores
    ) > 0


# ------------------------------------------------------------
# Test 3
# Temporary shift should not immediately become a regime.
#
# We intentionally use only the first 25 observations.
# This prevents a short-lived change from being accepted
# merely because it is different from the baseline.
# ------------------------------------------------------------

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_short_shift_is_not_confirmed(
    datasets,
    model_name,
):

    calibration_df, seasonal_df, _ = datasets

    model = get_models()[
        model_name
    ]

    calibration_scores = get_scores(
        calibration_df,
        model,
    )

    seasonal_scores = get_scores(
        seasonal_df,
        model,
    )

    detector = create_detector(
        calibration_scores
    )

    # Only a short candidate period.
    short_shift = seasonal_scores[
        :25
    ]

    feed_scores(
        detector,
        short_shift,
    )

    assert not detector.is_confirmed()


# ------------------------------------------------------------
# Test 4
# Slow temperature drift must not be blindly accepted.
#
# We inspect the detector's behavior over the complete drift
# sequence. The detector must not confirm a regime simply
# because the score distribution keeps moving.
# ------------------------------------------------------------

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_slow_drift_is_not_blindly_accepted(
    datasets,
    model_name,
):

    calibration_df, _, drift_df = datasets

    model = get_models()[
        model_name
    ]

    calibration_scores = get_scores(
        calibration_df,
        model,
    )

    drift_scores = get_scores(
        drift_df,
        model,
    )

    detector = create_detector(
        calibration_scores
    )

    results = feed_scores(
        detector,
        drift_scores,
    )

    # The important requirement here is that the detector
    # must not automatically promote the entire drift sequence
    # to a trusted normal regime.
    #
    # If it confirms, we inspect where confirmation occurred.
    if detector.is_confirmed():

        confirmation_indexes = [
            index
            for index, result in enumerate(
                results
            )
            if result["regime_confirmed"]
        ]

        assert confirmation_indexes

        first_confirmation = (
            confirmation_indexes[0]
        )

        # Confirmation should not happen immediately.
        assert first_confirmation >= 50


# ------------------------------------------------------------
# Test 5
# A confirmed regime must require actual shifted data.
# ------------------------------------------------------------

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_confirmation_contains_shifted_scores(
    datasets,
    model_name,
):

    calibration_df, seasonal_df, _ = datasets

    model = get_models()[
        model_name
    ]

    calibration_scores = get_scores(
        calibration_df,
        model,
    )

    seasonal_scores = get_scores(
        seasonal_df,
        model,
    )

    detector = create_detector(
        calibration_scores
    )

    feed_scores(
        detector,
        seasonal_scores,
    )

    assert detector.is_confirmed()

    confirmed_scores = np.asarray(
        detector.get_confirmed_scores(),
        dtype=float,
    )

    calibration_mean = np.mean(
        calibration_scores
    )

    confirmed_mean = np.mean(
        confirmed_scores
    )

    # The confirmed regime should actually be shifted from
    # the original calibration regime.
    assert not np.isclose(
        confirmed_mean,
        calibration_mean,
    )


# ------------------------------------------------------------
# Test 6
# Rejecting a candidate must preserve the original baseline.
# ------------------------------------------------------------

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_reject_candidate_preserves_baseline(
    datasets,
    model_name,
):

    calibration_df, seasonal_df, _ = datasets

    model = get_models()[
        model_name
    ]

    calibration_scores = get_scores(
        calibration_df,
        model,
    )

    seasonal_scores = get_scores(
        seasonal_df,
        model,
    )

    detector = create_detector(
        calibration_scores
    )

    state_before = detector.get_state()

    detector.candidate_scores.extend(
        seasonal_scores[:25]
    )

    detector.reject_candidate()

    state_after = detector.get_state()

    assert (
        state_after[
            "baseline_sample_count"
        ]
        == state_before[
            "baseline_sample_count"
        ]
    )

    assert (
        not state_after[
            "regime_confirmed"
        ]
    )

    assert (
        state_after[
            "candidate_sample_count"
        ]
        == 0
    )


# ------------------------------------------------------------
# Test 7
# Explicitly accepting a confirmed regime should replace
# the old baseline.
# ------------------------------------------------------------

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_accept_regime_replaces_baseline(
    datasets,
    model_name,
):

    calibration_df, seasonal_df, _ = datasets

    model = get_models()[
        model_name
    ]

    calibration_scores = get_scores(
        calibration_df,
        model,
    )

    seasonal_scores = get_scores(
        seasonal_df,
        model,
    )

    detector = create_detector(
        calibration_scores
    )

    feed_scores(
        detector,
        seasonal_scores,
    )

    if not detector.is_confirmed():
        pytest.skip(
            "Seasonal regime was not confirmed "
            "by the detector."
        )

    confirmed_scores = (
        detector.get_confirmed_scores()
    )

    detector.accept_regime()

    state = detector.get_state()

    assert (
        state[
            "baseline_sample_count"
        ]
        > 0
    )

    assert (
        state[
            "candidate_sample_count"
        ]
        == 0
    )

    assert (
        not state[
            "regime_confirmed"
        ]
    )

    new_baseline_mean = (
        state[
            "baseline_statistics"
        ]["mean"]
    )

    confirmed_mean = np.mean(
        confirmed_scores
    )

    assert np.isclose(
        new_baseline_mean,
        confirmed_mean,
        rtol=0.10,
        atol=1e-12,
    )


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

if __name__ == "__main__":

    pytest.main(
        [
            __file__,
            "-v",
        ]
    )