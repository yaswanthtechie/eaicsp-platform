"""
Model-specific adapters for Milestone 3 automated retraining.

These adapters provide a common interface to the four
served models without importing their independent `src`
packages directly.
"""

from __future__ import annotations

from typing import Any, Dict


MODEL_NAMES = (
    "forecast",
    "eta",
    "anomaly",
    "risk",
)


def check_drift(
    model_name: str,
    drift_score: float,
    threshold: float,
) -> Dict[str, Any]:
    """
    Evaluate whether a model has crossed its drift threshold.
    """

    if model_name not in MODEL_NAMES:
        raise ValueError(
            f"Unknown served model: {model_name}"
        )

    if drift_score < 0:
        raise ValueError(
            "drift_score cannot be negative."
        )

    drift_detected = (
        drift_score >= threshold
    )

    return {
        "model_name": model_name,
        "drift_score": drift_score,
        "threshold": threshold,
        "drift_detected": drift_detected,
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