"""
Milestone 3: Automated multi-model retraining orchestration.

Coordinates drift checks, retraining, evaluation, promotion,
and rollback-safe decisions for all served models.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict


@dataclass
class ModelRetrainingResult:
    """Result of one model's automated retraining cycle."""

    model_name: str
    status: str
    reason: str
    previous_version: str
    candidate_version: str | None = None
    candidate_score: float | None = None
    production_score: float | None = None
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "status": self.status,
            "reason": self.reason,
            "previous_version": self.previous_version,
            "candidate_version": self.candidate_version,
            "candidate_score": self.candidate_score,
            "production_score": self.production_score,
            "duration_ms": round(self.duration_ms, 3),
        }


class MultiModelRetrainingOrchestrator:
    """
    Orchestrates automated retraining for every served model.

    Each model supplies callbacks for:
        1. drift detection
        2. retraining
        3. candidate evaluation
        4. promotion

    A candidate is promoted only when its score is not worse
    than the current production score.
    """

    def __init__(
        self,
        models: Dict[str, Dict[str, Any]],
    ) -> None:
        self.models = models

    def run_model(
        self,
        model_name: str,
    ) -> Dict[str, Any]:
        """Run one model's drift/retrain/evaluate/promote workflow."""

        start = time.perf_counter()

        if model_name not in self.models:
            raise KeyError(
                f"Model '{model_name}' is not configured "
                "for automated retraining."
            )

        config = self.models[model_name]

        previous_version = str(
            config["get_version"]()
        )

        # --------------------------------------------------
        # 1. Drift detection
        # --------------------------------------------------
        drift_result = config["check_drift"]()

        if not drift_result.get("drift_detected", False):
            return ModelRetrainingResult(
                model_name=model_name,
                status="skipped",
                reason="drift_not_detected",
                previous_version=previous_version,
                duration_ms=(
                    time.perf_counter() - start
                ) * 1000.0,
            ).to_dict()

        # --------------------------------------------------
        # 2. Retraining
        # --------------------------------------------------
        candidate = config["retrain"]()

        candidate_version = str(
            candidate["version"]
        )

        candidate_score = float(
            candidate["score"]
        )

        # --------------------------------------------------
        # 3. Evaluate current production
        # --------------------------------------------------
        production_score = float(
            config["evaluate_production"]()
        )

        # --------------------------------------------------
        # 4. Promotion gate
        #
        # Higher score is assumed to be better.
        # --------------------------------------------------
        if candidate_score < production_score:
            return ModelRetrainingResult(
                model_name=model_name,
                status="rejected",
                reason="candidate_worse_than_production",
                previous_version=previous_version,
                candidate_version=candidate_version,
                candidate_score=candidate_score,
                production_score=production_score,
                duration_ms=(
                    time.perf_counter() - start
                ) * 1000.0,
            ).to_dict()

        # --------------------------------------------------
        # 5. Promote
        # --------------------------------------------------
        promoted_version = config["promote"](
            candidate_version
        )

        return ModelRetrainingResult(
            model_name=model_name,
            status="promoted",
            reason="candidate_better_or_equal",
            previous_version=previous_version,
            candidate_version=str(promoted_version),
            candidate_score=candidate_score,
            production_score=production_score,
            duration_ms=(
                time.perf_counter() - start
            ) * 1000.0,
        ).to_dict()

    def run_all(self) -> Dict[str, Any]:
        """
        Run automated retraining checks for every served model.

        One model failing does not prevent the other models
        from being processed.
        """

        started_at = time.time()

        results: Dict[str, Any] = {}

        for model_name in sorted(self.models):
            try:
                results[model_name] = self.run_model(
                    model_name
                )
            except Exception as exc:
                results[model_name] = {
                    "model_name": model_name,
                    "status": "error",
                    "reason": str(exc),
                }

        promoted = sum(
            1
            for result in results.values()
            if result.get("status") == "promoted"
        )

        retrained = sum(
            1
            for result in results.values()
            if result.get("status")
            in {"promoted", "rejected"}
        )

        return {
            "status": "completed",
            "started_at": started_at,
            "models_checked": len(results),
            "models_retrained": retrained,
            "models_promoted": promoted,
            "results": results,
        }