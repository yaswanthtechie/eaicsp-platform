# src/retraining.py

from typing import List, Dict
import numpy as np
from src.config import DRIFT_THRESHOLD

# Mean values of the Iris training dataset
TRAINING_MEAN = np.array([
    5.8433,
    3.0573,
    3.7580,
    1.1993,
])




def calculate_drift(
    recent_inputs: List[List[float]],
    training_mean: np.ndarray = TRAINING_MEAN,
) -> float:
    """
    Compare the mean of recent prediction inputs
    with the training-data mean.
    """

    if not recent_inputs:
        raise ValueError("recent_inputs cannot be empty")

    data = np.array(recent_inputs, dtype=float)

    if data.ndim != 2:
        raise ValueError("recent_inputs must be a list of feature lists")

    if data.shape[1] != len(training_mean):
        raise ValueError(
            f"Expected {len(training_mean)} features, "
            f"got {data.shape[1]}"
        )

    # Calculate mean of recent prediction inputs
    recent_mean = np.mean(data, axis=0)

    # Calculate relative drift for each feature
    drift_values = np.abs(
        recent_mean - training_mean
    ) / np.abs(training_mean)

    # Average drift across all features
    drift_score = float(np.mean(drift_values))

    return drift_score


def check_retraining_needed(
    recent_inputs: List[List[float]],
    training_mean: np.ndarray = TRAINING_MEAN,
    threshold: float = DRIFT_THRESHOLD,
) -> Dict:
    """
    Check whether recent prediction inputs have
    significantly drifted from the training data.
    """

    drift_score = calculate_drift(
        recent_inputs,
        training_mean,
    )

    retrain_needed = bool(
        np.isclose(
            drift_score,
            threshold,
            rtol=1e-9,
            atol=1e-9,
        )
        or drift_score >= threshold
    )

    if retrain_needed:
        reason = "Input feature drift detected"
    else:
        reason = "No significant drift detected"

    return {
        "retrain_needed": retrain_needed,
        "reason": reason,
        "drift_score": round(drift_score, 4),
        "threshold": threshold,
        "sample_count": len(recent_inputs),
    }


def manual_retrain_trigger() -> Dict:
    """
    Simulate a manual retraining trigger.

    This does not actually train a new model.
    """

    return {
        "status": "retraining_triggered",
        "message": "Model retraining has been manually triggered",
    }