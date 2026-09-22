"""
Model-specific adapters for Milestone 3 automated retraining.

These adapters provide a common interface to the four
served models without importing their independent `src`
packages directly.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np


MODEL_NAMES = (
    "forecast",
    "eta",
    "anomaly",
    "risk",
)


def _score_from_inputs(
    recent_inputs: Sequence[Any],
    baseline_mean: Optional[np.ndarray] = None,
) -> Optional[float]:
    """
    Compute a drift score from recent prediction inputs.

    Mirrors retraining.calculate_drift: mean relative deviation of the
    recent feature means from the baseline means.

    Returns None when there is not enough data to judge, which the caller
    must treat as "unknown", never as "no drift".
    """
    if not recent_inputs:
        return None

    rows = [
        row
        for row in recent_inputs
        if isinstance(row, (list, tuple)) and row
    ]

    if not rows:
        return None

    try:
        data = np.array(rows, dtype=float)
    except (TypeError, ValueError):
        return None

    if data.ndim != 2 or data.shape[0] < 2:
        return None

    if baseline_mean is None:
        # Without a stored baseline, compare the most recent half
        # of the window against the older half.
        split = data.shape[0] // 2
        baseline_mean = np.mean(data[:split], axis=0)
        recent_mean = np.mean(data[split:], axis=0)
    else:
        recent_mean = np.mean(data, axis=0)

    denominator = np.where(
        np.abs(baseline_mean) < 1e-9,
        1.0,
        np.abs(baseline_mean),
    )

    return float(
        np.mean(
            np.abs(recent_mean - baseline_mean)
            / denominator
        )
    )


def check_drift(
    model_name: str,
    threshold: float,
    drift_score: Optional[float] = None,
    recent_inputs: Optional[Sequence[Any]] = None,
    baseline_mean: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """
    Evaluate whether a model has crossed its drift threshold.

    Accepts either a precomputed drift_score or the raw recent_inputs
    to calculate the score.

    When there is not enough data to calculate drift, the result is
    reported as "insufficient_data" rather than "no drift".
    """

    if model_name not in MODEL_NAMES:
        raise ValueError(
            f"Unknown served model: {model_name}"
        )

    if drift_score is None:
        drift_score = _score_from_inputs(
            recent_inputs,
            baseline_mean,
        )

    if drift_score is None:
        return {
            "model_name": model_name,
            "drift_score": None,
            "threshold": threshold,
            "drift_detected": False,
            "reason": "insufficient_data",
            "sample_count": len(recent_inputs or []),
        }

    if drift_score < 0:
        raise ValueError(
            "drift_score cannot be negative."
        )

    return {
        "model_name": model_name,
        "drift_score": drift_score,
        "threshold": threshold,
        "drift_detected": drift_score >= threshold,
        "reason": "scored",
        "sample_count": len(recent_inputs or []),
    }


class ModelRetrainingAdapter:
    """
    Small abstraction around one model's retraining lifecycle.

    Real training/evaluation callbacks can be injected later
    without changing the orchestration layer.
    """

    def __init__(
        self,
        model_name: str,
        get_version,
        retrain,
        evaluate_production,
        promote,
        check_drift,
    ) -> None:
        self.model_name = model_name
        self.get_version = get_version
        self.retrain = retrain
        self.evaluate_production = evaluate_production
        self.promote = promote
        self.check_drift = check_drift

    def as_config(self) -> Dict[str, Any]:
        return {
            "get_version": self.get_version,
            "retrain": self.retrain,
            "evaluate_production": (
                self.evaluate_production
            ),
            "promote": self.promote,
            "check_drift": self.check_drift,
        }