"""
Controlled incident drill for the model-serving layer.

The drill temporarily injects a prediction failure into the
ModelManager, verifies that the failure is detected, restores
the original prediction path, and verifies recovery.

No model artifact is modified.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class IncidentDrillResult:
    model_name: str
    baseline_success: bool
    failure_detected: bool
    recovery_success: bool
    error_message: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "baseline_success": self.baseline_success,
            "failure_detected": self.failure_detected,
            "recovery_success": self.recovery_success,
            "error_message": self.error_message,
            "drill_passed": (
                self.baseline_success
                and self.failure_detected
                and self.recovery_success
            ),
        }


class IncidentSimulator:
    """
    Controlled model-serving failure simulator.

    The simulator temporarily replaces ModelManager.predict
    with a failing function.

    The original function is always restored after the drill.
    """

    def __init__(self, model_manager):
        self.model_manager = model_manager

    def run(
        self,
        model_name: str,
        payload: dict[str, Any],
    ) -> IncidentDrillResult:

        original_predict: Callable[..., Any] = (
            self.model_manager.predict
        )

        baseline_success = False
        failure_detected = False
        recovery_success = False
        error_message: str | None = None

        try:
            # -------------------------------------------------
            # Step 1: Baseline verification
            # -------------------------------------------------
            try:
                original_predict(
                    model_name=model_name,
                    payload=payload,
                )
                baseline_success = True

            except Exception as exc:
                error_message = (
                    f"Baseline prediction failed: {exc}"
                )

                return IncidentDrillResult(
                    model_name=model_name,
                    baseline_success=False,
                    failure_detected=False,
                    recovery_success=False,
                    error_message=error_message,
                )

            # -------------------------------------------------
            # Step 2: Inject controlled failure
            # -------------------------------------------------
            def failing_predict(*args, **kwargs):
                raise RuntimeError(
                    "SIMULATED_MODEL_SERVING_FAILURE"
                )

            self.model_manager.predict = failing_predict

            # -------------------------------------------------
            # Step 3: Detect failure
            # -------------------------------------------------
            try:
                self.model_manager.predict(
                    model_name=model_name,
                    payload=payload,
                )

            except RuntimeError as exc:
                if str(exc) == (
                    "SIMULATED_MODEL_SERVING_FAILURE"
                ):
                    failure_detected = True
                    error_message = str(exc)

            # -------------------------------------------------
            # Step 4: Recovery
            # -------------------------------------------------
            self.model_manager.predict = original_predict

            try:
                original_predict(
                    model_name=model_name,
                    payload=payload,
                )
                recovery_success = True

            except Exception as exc:
                error_message = (
                    f"Recovery prediction failed: {exc}"
                )

        finally:
            # Always restore the original prediction method.
            self.model_manager.predict = original_predict

        return IncidentDrillResult(
            model_name=model_name,
            baseline_success=baseline_success,
            failure_detected=failure_detected,
            recovery_success=recovery_success,
            error_message=error_message,
        )