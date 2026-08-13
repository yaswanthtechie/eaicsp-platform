import numpy as np
import pytest

from src.retraining import (
    TRAINING_MEAN,
    DRIFT_THRESHOLD,
    calculate_drift,
    check_retraining_needed,
    manual_retrain_trigger,
)


def test_calculate_drift_with_similar_inputs():
    """
    Recent inputs close to training mean should have low drift.
    """

    recent_inputs = [
        [5.84, 3.05, 3.76, 1.20],
        [5.85, 3.06, 3.75, 1.19],
        [5.84, 3.05, 3.76, 1.20],
    ]

    drift_score = calculate_drift(recent_inputs)

    assert isinstance(drift_score, float)
    assert drift_score < DRIFT_THRESHOLD


def test_calculate_drift_with_shifted_inputs():
    """
    Significantly shifted inputs should produce high drift.
    """

    recent_inputs = [
        [8.0, 6.0, 7.0, 4.0],
        [8.1, 6.1, 7.1, 4.1],
        [8.2, 6.2, 7.2, 4.2],
    ]

    drift_score = calculate_drift(recent_inputs)

    assert isinstance(drift_score, float)
    assert drift_score > DRIFT_THRESHOLD


def test_retraining_not_needed_when_drift_is_low():
    """
    Low input drift should not require retraining.
    """

    recent_inputs = [
        [5.84, 3.05, 3.76, 1.20],
        [5.85, 3.06, 3.75, 1.19],
        [5.84, 3.05, 3.76, 1.20],
    ]

    result = check_retraining_needed(recent_inputs)

    assert result["retrain_needed"] is False
    assert result["reason"] == "No significant drift detected"
    assert result["drift_score"] < result["threshold"]


def test_retraining_needed_when_drift_is_high():
    """
    Significant input drift should require retraining.
    """

    recent_inputs = [
        [8.0, 6.0, 7.0, 4.0],
        [8.1, 6.1, 7.1, 4.1],
        [8.2, 6.2, 7.2, 4.2],
    ]

    result = check_retraining_needed(recent_inputs)

    assert result["retrain_needed"] is True
    assert result["reason"] == "Input feature drift detected"
    assert result["drift_score"] > result["threshold"]


def test_retraining_result_contains_required_fields():
    """
    Retraining check should return all required monitoring fields.
    """

    recent_inputs = [
        [5.84, 3.05, 3.76, 1.20],
        [5.85, 3.06, 3.75, 1.19],
    ]

    result = check_retraining_needed(recent_inputs)

    assert "retrain_needed" in result
    assert "reason" in result
    assert "drift_score" in result
    assert "threshold" in result
    assert "sample_count" in result


def test_retraining_sample_count():
    """
    Result should report the number of recent prediction samples.
    """

    recent_inputs = [
        [5.84, 3.05, 3.76, 1.20],
        [5.85, 3.06, 3.75, 1.19],
        [5.83, 3.04, 3.77, 1.21],
    ]

    result = check_retraining_needed(recent_inputs)

    assert result["sample_count"] == 3


def test_retraining_threshold_is_returned():
    """
    Configured drift threshold should be returned.
    """

    recent_inputs = [
        [5.84, 3.05, 3.76, 1.20],
    ]

    result = check_retraining_needed(recent_inputs)

    assert result["threshold"] == DRIFT_THRESHOLD


def test_custom_drift_threshold():
    """
    check_retraining_needed should support a custom threshold.
    """

    recent_inputs = [
        [6.5, 3.5, 4.5, 1.5],
        [6.6, 3.6, 4.6, 1.6],
    ]

    result = check_retraining_needed(
        recent_inputs,
        threshold=0.01,
    )

    assert result["retrain_needed"] is True
    assert result["threshold"] == 0.01


def test_calculate_drift_accepts_custom_training_mean():
    """
    Drift calculation should support a custom reference mean.
    """

    training_mean = np.array([
        5.0,
        3.0,
        4.0,
        1.0,
    ])

    recent_inputs = [
        [5.0, 3.0, 4.0, 1.0],
        [5.0, 3.0, 4.0, 1.0],
    ]

    drift_score = calculate_drift(
        recent_inputs,
        training_mean=training_mean,
    )

    assert drift_score == 0.0


def test_empty_inputs_raise_error():
    """
    Empty prediction input history should raise ValueError.
    """

    with pytest.raises(ValueError, match="recent_inputs cannot be empty"):
        calculate_drift([])


def test_invalid_input_dimension_raises_error():
    """
    Input must be a list of feature lists.
    """

    with pytest.raises(
        ValueError,
        match="recent_inputs must be a list of feature lists",
    ):
        calculate_drift([1, 2, 3, 4])


def test_wrong_feature_count_raises_error():
    """
    Iris model expects exactly 4 input features.
    """

    recent_inputs = [
        [5.8, 3.0, 3.7],
        [5.9, 3.1, 3.8],
    ]

    with pytest.raises(
        ValueError,
        match="Expected 4 features",
    ):
        calculate_drift(recent_inputs)


def test_manual_retrain_trigger():
    """
    Manual retraining endpoint/function should return
    the simulated retraining status.
    """

    result = manual_retrain_trigger()

    assert result["status"] == "retraining_triggered"
    assert "message" in result
    assert "manually" in result["message"].lower()