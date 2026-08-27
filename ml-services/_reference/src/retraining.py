from typing import List, Dict, Callable
import logging

import numpy as np

from src.config import DRIFT_THRESHOLD


logger = logging.getLogger(__name__)


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

    if not recent_inputs:
        raise ValueError(
            "recent_inputs cannot be empty"
        )

    data = np.array(
        recent_inputs,
        dtype=float,
    )

    if data.ndim != 2:
        raise ValueError(
            "recent_inputs must be a list of feature lists"
        )

    if data.shape[1] != len(training_mean):
        raise ValueError(
            f"Expected {len(training_mean)} features, "
            f"got {data.shape[1]}"
        )

    recent_mean = np.mean(
        data,
        axis=0,
    )

    drift_values = (
        np.abs(
            recent_mean - training_mean
        )
        / np.abs(training_mean)
    )

    return float(
        np.mean(drift_values)
    )


def check_retraining_needed(
    recent_inputs: List[List[float]],
    training_mean: np.ndarray = TRAINING_MEAN,
    threshold: float = DRIFT_THRESHOLD,
) -> Dict:

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
        "drift_score": round(
            drift_score,
            4,
        ),
        "threshold": threshold,
        "sample_count": len(recent_inputs),
    }


def automated_retrain(
    recent_inputs: List[List[float]],
    retrain_callback: Callable,
) -> Dict:
    """
    R5 automated retraining.

    Drift
       ↓
    threshold crossed
       ↓
    train
       ↓
    register
       ↓
    staging
       ↓
    production
    """

    result = check_retraining_needed(
        recent_inputs
    )

    logger.info(
        "Drift check result: %s",
        result,
    )

    if not result["retrain_needed"]:

        return {
            "status": "skipped",
            "reason": result["reason"],
            "drift_score": result["drift_score"],
            "threshold": result["threshold"],
            "sample_count": result["sample_count"],
        }

    logger.warning(
        "DRIFT THRESHOLD EXCEEDED - "
        "AUTOMATED RETRAINING STARTED"
    )

    new_version = retrain_callback()

    logger.warning(
        "AUTOMATED RETRAINING COMPLETED - "
        "VERSION %s PROMOTED",
        new_version,
    )

    return {
        "status": "retrained",
        "reason": result["reason"],
        "drift_score": result["drift_score"],
        "threshold": result["threshold"],
        "sample_count": result["sample_count"],
        "new_model_version": str(
            new_version
        ),
    }


def manual_retrain_trigger() -> Dict:

    return {
        "status": "retraining_triggered",
        "message": (
            "Model retraining has been manually triggered"
        ),
    }