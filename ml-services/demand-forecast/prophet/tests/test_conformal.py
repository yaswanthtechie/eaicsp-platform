import numpy as np
import pytest

from src.conformal import (
    build_relative_conformal_interval,
    calibration_radius,
    conformal_quantile,
    empirical_relative_interval,
    evaluate_interval_methods,
    interval_coverage,
    interval_pinball_loss,
    pinball_loss,
    relative_nonconformity_scores,
)

def test_relative_nonconformity_scores():
    actual = np.array([105.0, 90.0])
    predicted = np.array([100.0, 100.0])

    scores = relative_nonconformity_scores(
        actual,
        predicted,
    )

    np.testing.assert_allclose(
        scores,
        [0.05, 0.10],
    )


def test_conformal_quantile_uses_finite_sample_rank():
    scores = np.array(
        [0.01, 0.02, 0.03, 0.04, 0.05]
    )

    result = conformal_quantile(
        scores,
        coverage=0.80,
    )

    assert result == pytest.approx(0.05)


def test_conformal_interval_contains_prediction():
    predicted = np.array(
        [100.0, 200.0]
    )

    lower, upper = (
        build_relative_conformal_interval(
            predicted,
            radius=0.10,
        )
    )

    np.testing.assert_allclose(
        lower,
        [90.0, 180.0],
    )

    np.testing.assert_allclose(
        upper,
        [110.0, 220.0],
    )


def test_interval_coverage():
    actual = np.array(
        [95.0, 100.0, 105.0, 120.0]
    )

    lower = np.array(
        [90.0, 90.0, 90.0, 90.0]
    )

    upper = np.array(
        [110.0, 110.0, 110.0, 110.0]
    )

    coverage = interval_coverage(
        actual,
        lower,
        upper,
    )

    assert coverage == pytest.approx(0.75)


def test_pinball_loss_zero_when_prediction_matches():
    actual = np.array(
        [10.0, 20.0, 30.0]
    )

    prediction = actual.copy()

    loss = pinball_loss(
        actual,
        prediction,
        quantile=0.5,
    )

    assert loss == pytest.approx(0.0)


def test_interval_pinball_loss_is_non_negative():
    actual = np.array(
        [100.0, 110.0, 90.0]
    )

    lower = np.array(
        [90.0, 100.0, 80.0]
    )

    upper = np.array(
        [110.0, 120.0, 100.0]
    )

    loss = interval_pinball_loss(
        actual,
        lower,
        upper,
        coverage=0.80,
    )

    assert loss >= 0.0

def test_calibration_radius_uses_calibration_scores():
    actual = np.array([
        102.0,
        104.0,
        105.0,
        108.0,
        110.0,
    ])

    predicted = np.array([
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
    ])

    radius = calibration_radius(
        actual,
        predicted,
        coverage=0.80,
    )

    assert radius == pytest.approx(0.10)

def test_empirical_interval_and_conformal_evaluation():
    calibration_actual = np.array([
        102.0,
        104.0,
        105.0,
        108.0,
        110.0,
    ])

    calibration_predicted = np.array([
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
    ])

    evaluation_actual = np.array([
        103.0,
        107.0,
        112.0,
        96.0,
    ])

    evaluation_predicted = np.array([
        100.0,
        100.0,
        100.0,
        100.0,
    ])

    result = evaluate_interval_methods(
        calibration_actual=calibration_actual,
        calibration_predicted=calibration_predicted,
        evaluation_actual=evaluation_actual,
        evaluation_predicted=evaluation_predicted,
        coverage=0.80,
    )

    assert result["coverage"] == pytest.approx(0.80)

    assert (
        0.0
        <= result["before"]["coverage"]
        <= 1.0
    )

    assert (
        0.0
        <= result["after"]["coverage"]
        <= 1.0
    )

    assert (
        result["calibration_radius"]
        >= 0.0
    )

    assert (
        result["before"]["pinball_loss"]
        >= 0.0
    )

    assert (
        result["after"]["pinball_loss"]
        >= 0.0
    )        