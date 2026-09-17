from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Dict


@dataclass
class ModelRetrainingResult:
    """
    Result of one model's automated retraining workflow.

    Workflow:
        drift detection
        -> retraining
        -> production evaluation
        -> candidate comparison
        -> promotion
        -> post-promotion validation
        -> rollback when validation fails
    """

    model_name: str
    status: str
    reason: str
    previous_version: str

    candidate_version: str | None = None
    candidate_score: float | None = None
    production_score: float | None = None
    promoted_version: str | None = None
    rollback_version: str | None = None
    validation_score: float | None = None
    duration_ms: float = 0.0

    def __getitem__(self, key: str) -> Any:
        """
        Allow dictionary-style access for backward compatibility
        with existing tests and API responses.
        """
        return getattr(self, key)


class MultiModelRetrainingOrchestrator:
    """
    Coordinates automated retraining for multiple served models.

    Each model configuration may provide:

        get_version()
        check_drift()
        retrain()
        evaluate_production()
        promote(version)

    Optional safety callbacks:

        validate_promoted()
        rollback(version)

    The metric direction is controlled by:

        higher_is_better=True
        higher_is_better=False

    A candidate must be strictly better than production.
    Ties are never promoted.
    """

    def __init__(self, models: Dict[str, Dict[str, Any]]) -> None:
        self.models = models

    @staticmethod
    def _is_strictly_better(
        candidate_score: float,
        production_score: float,
        higher_is_better: bool,
    ) -> bool:
        """
        Return True only when the candidate is strictly better.

        Higher-is-better:
            candidate > production

        Lower-is-better:
            candidate < production

        Equal scores are never considered an improvement.
        """

        if higher_is_better:
            return candidate_score > production_score

        return candidate_score < production_score

    @staticmethod
    def _rollback(
        config: Dict[str, Any],
        previous_version: str,
    ) -> str:
        """
        Roll back to the previous production version.

        A rollback callback is required when a post-promotion
        validation failure occurs.
        """

        rollback = config.get("rollback")

        if rollback is None:
            raise RuntimeError(
                "Rollback callback is not configured."
            )

        rollback_result = rollback(previous_version)

        if rollback_result is None:
            return previous_version

        return str(rollback_result)

    def run_model(self, model_name: str) -> ModelRetrainingResult:
        """
        Run the complete retraining workflow for one model.
        """

        if model_name not in self.models:
            raise KeyError(
                f"Unknown model: {model_name}"
            )

        started = perf_counter()
        config = self.models[model_name]

        previous_version = str(
            config["get_version"]()
        )

        try:
            # -------------------------------------------------
            # 1. Drift detection
            # -------------------------------------------------
            drift_result = config["check_drift"]()

            if not drift_result.get(
                "drift_detected",
                False,
            ):
                return ModelRetrainingResult(
                    model_name=model_name,
                    status="skipped",
                    reason="drift_not_detected",
                    previous_version=previous_version,
                    duration_ms=(
                        perf_counter() - started
                    )
                    * 1000,
                )

            # -------------------------------------------------
            # 2. Retrain
            # -------------------------------------------------
            candidate = config["retrain"]()

            candidate_version = str(
                candidate["version"]
            )

            candidate_score = float(
                candidate["score"]
            )

            # -------------------------------------------------
            # 3. Evaluate current production
            # -------------------------------------------------
            production_score = float(
                config["evaluate_production"]()
            )

            higher_is_better = bool(
                config.get(
                    "higher_is_better",
                    True,
                )
            )

            # -------------------------------------------------
            # 4. Candidate quality gate
            # -------------------------------------------------
            if not self._is_strictly_better(
                candidate_score=candidate_score,
                production_score=production_score,
                higher_is_better=higher_is_better,
            ):
                return ModelRetrainingResult(
                    model_name=model_name,
                    status="rejected",
                    reason="candidate_worse_than_production",
                    previous_version=previous_version,
                    candidate_version=candidate_version,
                    candidate_score=candidate_score,
                    production_score=production_score,
                    duration_ms=(
                        perf_counter() - started
                    )
                    * 1000,
                )

            # -------------------------------------------------
            # 5. Promote candidate
            # -------------------------------------------------
            promoted_version = str(
                config["promote"](
                    candidate_version
                )
            )

            # -------------------------------------------------
            # 6. Post-promotion validation
            # -------------------------------------------------
            validate_promoted = config.get(
                "validate_promoted"
            )

            if validate_promoted is None:
                # Backward-compatible behavior:
                # if no validation callback exists,
                # promotion is considered successful.
                return ModelRetrainingResult(
                    model_name=model_name,
                    status="promoted",
                    reason="candidate_better_than_production",
                    previous_version=previous_version,
                    candidate_version=candidate_version,
                    candidate_score=candidate_score,
                    production_score=production_score,
                    promoted_version=promoted_version,
                    duration_ms=(
                        perf_counter() - started
                    )
                    * 1000,
                )

            validation_score = float(
                validate_promoted()
            )

            # -------------------------------------------------
            # 7. Validate promoted model against production
            # -------------------------------------------------
            validation_passed = self._is_strictly_better(
                candidate_score=validation_score,
                production_score=production_score,
                higher_is_better=higher_is_better,
            )

            if validation_passed:
                return ModelRetrainingResult(
                    model_name=model_name,
                    status="promoted",
                    reason="post_promotion_validation_passed",
                    previous_version=previous_version,
                    candidate_version=candidate_version,
                    candidate_score=candidate_score,
                    production_score=production_score,
                    promoted_version=promoted_version,
                    validation_score=validation_score,
                    duration_ms=(
                        perf_counter() - started
                    )
                    * 1000,
                )

            # -------------------------------------------------
            # 8. Validation failed -> rollback
            # -------------------------------------------------
            rollback_version = self._rollback(
                config,
                previous_version,
            )

            return ModelRetrainingResult(
                model_name=model_name,
                status="rolled_back",
                reason="post_promotion_validation_failed",
                previous_version=previous_version,
                candidate_version=candidate_version,
                candidate_score=candidate_score,
                production_score=production_score,
                promoted_version=promoted_version,
                rollback_version=rollback_version,
                validation_score=validation_score,
                duration_ms=(
                    perf_counter() - started
                )
                * 1000,
            )

        except Exception as exc:
            return ModelRetrainingResult(
                model_name=model_name,
                status="error",
                reason=str(exc),
                previous_version=previous_version,
                duration_ms=(
                    perf_counter() - started
                )
                * 1000,
            )

    def run_all(self) -> Dict[str, Any]:
        """
        Run retraining independently for every configured model.

        One model failing does not stop the remaining models.
        """

        results: Dict[str, ModelRetrainingResult] = {}

        models_retrained = 0
        models_promoted = 0
        models_rolled_back = 0

        for model_name in sorted(self.models):
            result = self.run_model(model_name)

            results[model_name] = result

            if result.status in {
                "promoted",
                "rejected",
                "rolled_back",
            }:
                models_retrained += 1

            if result.status == "promoted":
                models_promoted += 1

            if result.status == "rolled_back":
                models_rolled_back += 1

        return {
            "status": "completed",
            "models_checked": len(self.models),
            "models_retrained": models_retrained,
            "models_promoted": models_promoted,
            "models_rolled_back": models_rolled_back,
            "results": {
                model_name: result.__dict__
                for model_name, result in results.items()
            },
        }