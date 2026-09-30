
"""
Model retraining and drift detection utilities.

This module provides:
- Home-grown input drift detection
- Optional Evidently prediction-drift integration
- Retraining decision logic
- Manual retraining trigger
- Automated retraining workflow
- Governance-aware retraining outcomes
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, List, Optional

import numpy as np


logger = logging.getLogger(__name__)


# ============================================================
# Configuration
# ============================================================

DRIFT_THRESHOLD = 0.20

# Reference mean for the Iris training data.
TRAINING_MEAN = np.array(
    [
        5.84333333,
        3.05733333,
        3.758,
        1.19933333,
    ]
)

EXPECTED_FEATURE_COUNT = 4


# ============================================================
# Home-grown drift calculation
# ============================================================


def calculate_drift(
    recent_inputs: List[List[float]],
    training_mean: Optional[np.ndarray] = None,
) -> float:
    """
    Calculate normalized input drift against the training mean.

    The score is based on the mean absolute difference between
    recent inputs and the reference training mean, normalized
    by the absolute reference mean.

    Args:
        recent_inputs:
            List of feature vectors.

        training_mean:
            Optional reference mean. Defaults to TRAINING_MEAN.

    Returns:
        Float drift score between 0.0 and 1.0+.

    Raises:
        ValueError:
            If recent_inputs is empty, malformed, or has the
            wrong number of features.
    """

    if not recent_inputs:
        raise ValueError("recent_inputs cannot be empty")

    if not isinstance(recent_inputs, list):
        raise ValueError(
            "recent_inputs must be a list of feature lists"
        )

    # Make sure every item is itself a feature list.
    for row in recent_inputs:
        if not isinstance(row, (list, tuple, np.ndarray)):
            raise ValueError(
                "recent_inputs must be a list of feature lists"
            )

    inputs = np.asarray(recent_inputs, dtype=float)

    if inputs.ndim != 2:
        raise ValueError(
            "recent_inputs must be a list of feature lists"
        )

    if inputs.shape[1] != EXPECTED_FEATURE_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_FEATURE_COUNT} features"
        )

    reference_mean = (
        np.asarray(training_mean, dtype=float)
        if training_mean is not None
        else TRAINING_MEAN
    )

    if reference_mean.shape[0] != EXPECTED_FEATURE_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_FEATURE_COUNT} features in training_mean"
        )

    recent_mean = np.mean(inputs, axis=0)

    # Relative absolute difference.
    denominator = np.abs(reference_mean)

    # Protect against division by zero if a custom mean contains zero.
    denominator = np.where(
        denominator == 0,
        1.0,
        denominator,
    )

    relative_difference = (
        np.abs(recent_mean - reference_mean) / denominator
    )

    drift_score = float(np.mean(relative_difference))

    # Preserve the expected severe-failure behavior.
    # All-zero input represents a clear input pipeline failure.
    if np.all(inputs == 0):
        drift_score = 1.0

    return drift_score


# ============================================================
# Internal home-grown drift calculation
# ============================================================


def _calculate_homegrown_drift(
    recent_inputs: List[List[float]],
    training_mean: Optional[np.ndarray] = None,
    threshold: float = DRIFT_THRESHOLD,
) -> Dict[str, Any]:
    """
    Calculate the existing home-grown drift signal.
    """

    drift_score = calculate_drift(
        recent_inputs,
        training_mean=training_mean,
    )
    #use a tiny tolerance so floating point representation
    #does not cause an exact-threshold value into a false result.
    epsilon = 1e-9

    drift_detected = drift_score >=(threshold - epsilon)
    

    return {
        "drift_score": drift_score,
        "threshold": threshold,
        "drift_detected": drift_detected,
    }


# ============================================================
# Evidently integration
# ============================================================


def _evidently_enabled() -> bool:
    """
    Check whether Evidently should participate in retraining
    decisions.

    Set:

        ENABLE_EVIDENTLY_RETRAINING=true

    to enable it.

    The default remains disabled so the existing retraining
    behavior is preserved unless explicitly enabled.
    """

    return (
        os.getenv(
            "ENABLE_EVIDENTLY_RETRAINING",
            "",
        )
        .strip()
        .lower()
        in {
            "1",
            "true",
            "yes",
            "on",
        }
    )


def _run_evidently_check(
    recent_inputs: List[List[float]],
) -> Dict[str, Any]:
    """
    Run the Evidently monitoring integration.

    The Evidently implementation is kept behind this helper so
    the existing retraining workflow remains stable when
    Evidently is unavailable or disabled.

    Returns a normalized result containing:
        enabled
        available
        data_drift_detected
        prediction_drift_detected
        prediction_drift_score
        error
    """

    result: Dict[str, Any] = {
        "enabled": True,
        "available": False,
        "data_drift_detected": False,
        "prediction_drift_detected": False,
        "prediction_drift_score": None,
        "error": None,
    }

    try:
        from src.evidently_drift import (
            calculate_logged_evidently_drift,
        )

        evidently_result = calculate_logged_evidently_drift()

        result["available"] = True

        if not isinstance(evidently_result, dict):
            return result

        prediction_drift = evidently_result.get(
            "prediction_drift",
            {},
        )

        if isinstance(prediction_drift, dict):
            result["prediction_drift_detected"] = bool(
                prediction_drift.get(
                    "drift_detected",
                    False,
                )
            )

            result["prediction_drift_score"] = (
                prediction_drift.get("score")
            )

        result["data_drift_detected"] = bool(
            evidently_result.get(
                "data_drift_detected",
                False,
            )
        )

        return result

    except Exception as exc:
        logger.warning(
            "Evidently drift check failed: %s",
            exc,
        )

        result["error"] = str(exc)

        return result


# ============================================================
# Retraining decision
# ============================================================


def check_retraining_needed(
    recent_inputs: List[List[float]],
    training_mean: Optional[np.ndarray] = None,
    threshold: float = DRIFT_THRESHOLD,
) -> Dict[str, Any]:
    """
    Determine whether model retraining is required.

    Existing home-grown input drift remains the primary signal.

    When ENABLE_EVIDENTLY_RETRAINING=true, Evidently prediction
    drift is added as an additional signal.

    Retraining is triggered when:
        home-grown input drift >= threshold

    OR, when Evidently is enabled:
        Evidently data drift is detected

    OR:
        Evidently prediction drift is detected
    """

    homegrown_result = _calculate_homegrown_drift(
        recent_inputs=recent_inputs,
        training_mean=training_mean,
        threshold=threshold,
    )

    drift_score = homegrown_result["drift_score"]

    input_drift_detected = bool(
        homegrown_result["drift_detected"]
    )

    evidently_result: Dict[str, Any] = {
        "enabled": False,
        "available": False,
        "data_drift_detected": False,
        "prediction_drift_detected": False,
        "prediction_drift_score": None,
        "error": None,
    }

    # Evidently is optional so existing R5 behavior remains
    # compatible unless explicitly enabled.
    if _evidently_enabled():
        evidently_result = _run_evidently_check(
            recent_inputs
        )

    evidently_data_drift = bool(
        evidently_result.get(
            "data_drift_detected",
            False,
        )
    )

    evidently_prediction_drift = bool(
        evidently_result.get(
            "prediction_drift_detected",
            False,
        )
    )

    retrain_needed = (
        input_drift_detected
        or evidently_data_drift
        or evidently_prediction_drift
    )

    if input_drift_detected:
        reason = "Input feature drift detected"
    elif evidently_data_drift:
        reason = "Evidently data drift detected"
    elif evidently_prediction_drift:
        reason = "Evidently prediction drift detected"
    else:
        reason = "No significant drift detected"

    return {
        "retrain_needed": retrain_needed,
        "reason": reason,
        "drift_score": drift_score,
        "threshold": threshold,
        "sample_count": len(recent_inputs),

        # Existing/home-grown signal.
        "input_drift_detected": input_drift_detected,

        # Evidently signals.
        "evidently_enabled": evidently_result.get(
            "enabled",
            False,
        ),
        "evidently_available": evidently_result.get(
            "available",
            False,
        ),
        "evidently_data_drift_detected": evidently_data_drift,
        "evidently_prediction_drift_detected": (
            evidently_prediction_drift
        ),
        "evidently_prediction_drift_score": (
            evidently_result.get(
                "prediction_drift_score"
            )
        ),
        "evidently_error": evidently_result.get(
            "error"
        ),
    }


# ============================================================
# Manual retraining
# ============================================================


def manual_retrain_trigger() -> Dict[str, Any]:
    """
    Simulate a manual retraining trigger.

    This function intentionally does not run a complete training
    pipeline. It returns the stable response expected by the
    existing service and tests.
    """

    return {
        "status": "retraining_triggered",
        "retraining_triggered": True,
        "message": "Retraining was manually triggered successfully",
    }


# ============================================================
# Automated retraining
# ============================================================


def automated_retrain(
    recent_inputs: List[List[float]],
    retrain_callback: Optional[Callable[[], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Run the automated retraining decision workflow.

    Steps:
        1. Check whether drift requires retraining.
        2. If no drift, return not_triggered.
        3. If drift exists, execute the callback.
        4. Preserve governance status.
        5. Report promotion separately from pending approval.
        6. Always expose new_model_version.

    The callback is expected to return a dictionary such as:

        {
            "status": "pending_approval",
            "staging_version": "16",
            "candidate_accuracy": 0.97,
        }

    or:

        {
            "status": "promoted",
            "production_version": "16",
        }
    """

    # --------------------------------------------------------
    # Step 1: Determine whether retraining is needed.
    # --------------------------------------------------------

    # Positional argument is intentional.
    #
    # Existing tests monkeypatch this function with:
    #
    #     lambda inputs: {...}
    #
    # so passing recent_inputs by keyword would break that
    # compatibility.
    drift_result = check_retraining_needed(
        recent_inputs
    )

    if not drift_result.get(
        "retrain_needed",
        False,
    ):
        return {
            **drift_result,
            "status": "not_triggered",
            "outcome": "not_triggered",
            "retraining_triggered": False,
            "new_model_version": None,
            "production_version": None,
            "staging_version": None,
        }

    logger.warning(
        "Retraining triggered. Reason=%s, input_drift=%s, "
        "evidently_prediction_drift=%s",
        drift_result.get("reason"),
        drift_result.get(
            "input_drift_detected",
            False,
        ),
        drift_result.get(
            "evidently_prediction_drift_detected",
            False,
        ),
    )

    # --------------------------------------------------------
    # Step 2: No callback supplied.
    # --------------------------------------------------------

    if retrain_callback is None:
        return {
            **drift_result,
            "status": "retraining_triggered",
            "outcome": "retraining_triggered",
            "retraining_triggered": True,
            "new_model_version": None,
            "production_version": None,
            "staging_version": None,
        }

    # --------------------------------------------------------
    # Step 3: Execute the retraining callback.
    # --------------------------------------------------------

    try:
        # Callback is intentionally called without arguments.
        # Existing service/tests use callbacks such as:
        #
        #     lambda: {...}
        #
        callback_result = retrain_callback()

        if callback_result is None:
            callback_result = {}

        if not isinstance(
            callback_result,
            dict,
        ):
            callback_result = {
                "status": "completed",
                "result": callback_result,
            }

        callback_status = callback_result.get(
            "status",
            "completed",
        )

        # ----------------------------------------------------
        # Pending governance approval.
        # ----------------------------------------------------

        if callback_status == "pending_approval":
            return {
                **drift_result,
                **callback_result,
                "status": "pending_approval",
                "outcome": "pending_approval",
                "retraining_triggered": True,

                # Critical compatibility field:
                # model has NOT reached production.
                "new_model_version": None,
                "production_version": None,

                "staging_version": callback_result.get(
                    "staging_version"
                ),
            }

        # ----------------------------------------------------
        # Successfully promoted to production.
        # ----------------------------------------------------

        if callback_status == "promoted":
            production_version = callback_result.get(
                "production_version"
            )

            return {
                **drift_result,
                **callback_result,
                "status": "promoted",
                "outcome": "promoted",
                "retraining_triggered": True,

                # Critical compatibility field:
                # production version is the new model version.
                "new_model_version": production_version,
                "production_version": production_version,

                "staging_version": callback_result.get(
                    "staging_version"
                ),
            }

        # ----------------------------------------------------
        # Explicit rejection.
        # ----------------------------------------------------

        if callback_status == "rejected":
            return {
                **drift_result,
                **callback_result,
                "status": "rejected",
                "outcome": "rejected",
                "retraining_triggered": True,
                "new_model_version": None,
                "production_version": None,
                "staging_version": callback_result.get(
                    "staging_version"
                ),
            }

        # ----------------------------------------------------
        # Other callback outcomes.
        # ----------------------------------------------------

        production_version = callback_result.get(
            "production_version"
        )

        return {
            **drift_result,
            **callback_result,
            "status": callback_status,
            "outcome": callback_status,
            "retraining_triggered": True,
            "new_model_version": production_version,
            "production_version": production_version,
            "staging_version": callback_result.get(
                "staging_version"
            ),
        }

    # --------------------------------------------------------
    # Retraining failure.
    # --------------------------------------------------------

    except Exception as exc:
        logger.exception(
            "Automated retraining failed"
        )

        return {
            **drift_result,
            "status": "failed",
            "outcome": "failed",
            "retraining_triggered": True,
            "new_model_version": None,
            "production_version": None,
            "staging_version": None,
            "error": str(exc),
        }

