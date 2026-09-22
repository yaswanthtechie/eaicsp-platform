"""
FastAPI router for unified multi-model serving.

Responsibilities:
- List models
- Model information
- Production prediction
- Deterministic A/B prediction
- A/B metrics
- Statistical A/B verdict
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from src.ab_testing import (
    assign_variant,
    compare_variants,
    deterministic_bucket,
)
from src.experiment import ABExperiment
from src.model_manager import ModelManager
from src.schemas import ModelPredictionRequest


# ============================================================
# Helpers
# ============================================================

def _get_ab_experiment(
    model_manager: ModelManager,
    model_name: str,
) -> ABExperiment:
    """
    Get the configured A/B experiment for a model.
    """

    getter = getattr(
        model_manager,
        "get_ab_experiment",
        None,
    )

    if getter is None:
        raise HTTPException(
            status_code=500,
            detail=(
                "ModelManager does not expose "
                "get_ab_experiment()."
            ),
        )

    try:
        experiment = getter(
            model_name
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    if not isinstance(
        experiment,
        ABExperiment,
    ):
        raise HTTPException(
            status_code=500,
            detail=(
                f"Invalid A/B experiment configuration "
                f"for model '{model_name}'."
            ),
        )

    return experiment


def _empty_variant_metrics() -> Dict[str, Any]:
    """
    Return an empty metrics structure.
    """

    return {
        "requests": 0,
        "successes": 0,
        "failures": 0,
        "average_latency_ms": 0.0,
        "success_rate": 0.0,
    }


# ============================================================
# Router
# ============================================================

def create_router(
    model_manager: ModelManager,
) -> APIRouter:
    """
    Create the unified multi-model API router.
    """

    router = APIRouter(
        prefix="/models",
        tags=["Multi-Model Serving"],
    )

    # ========================================================
    # List Models
    # ========================================================

    @router.get("")
    def list_models() -> Dict[str, Any]:
        """
        Return all registered models.
        """

        return {
            "models": model_manager.list_models()
        }

    # ========================================================
    # Model Information
    # ========================================================

    @router.get("/{model_name}")
    def get_model(
        model_name: str,
    ) -> Dict[str, Any]:
        """
        Return information about one model.
        """

        try:
            return model_manager.get_model_info(
                model_name
            )

        except KeyError as exc:
            raise HTTPException(
                status_code=404,
                detail=str(exc),
            ) from exc

    # ========================================================
    # Normal Production Prediction
    # ========================================================

    @router.post("/{model_name}/predict")
    def predict(
        model_name: str,
        request: ModelPredictionRequest,
    ) -> Dict[str, Any]:
        """
        Run prediction using the current production version.
        """

        try:
            return model_manager.predict(
                model_name=model_name,
                payload=request.payload,
            )

        except KeyError as exc:
            raise HTTPException(
                status_code=404,
                detail=str(exc),
            ) from exc

        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

    # ========================================================
    # A/B Prediction
    # ========================================================

    @router.post(
        "/{model_name}/ab-test/predict"
    )
    def ab_test_predict(
        model_name: str,
        request: ModelPredictionRequest,
    ) -> Dict[str, Any]:
        """
        Run one request through the configured A/B experiment.

        Routing is deterministic using request_id.

        variant_a = control
        variant_b = challenger
        """

        # ----------------------------------------------------
        # Validate request_id
        # ----------------------------------------------------

        request_id = getattr(
            request,
            "request_id",
            None,
        )

        if (
            not isinstance(
                request_id,
                str,
            )
            or not request_id.strip()
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "request_id is required for "
                    "A/B testing and must not be empty."
                ),
            )

        request_id = request_id.strip()

        # ----------------------------------------------------
        # Load experiment
        # ----------------------------------------------------

        experiment = _get_ab_experiment(
            model_manager,
            model_name,
        )

        # ----------------------------------------------------
        # Assign variant
        # ----------------------------------------------------

        try:
            bucket = deterministic_bucket(
                request_id
            )

            selected_variant = assign_variant(
                request_id,
                experiment,
            )

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

        # ----------------------------------------------------
        # Validate selected version exists
        # ----------------------------------------------------

        try:
            model_manager.get_version_adapter(
                model_name=model_name,
                version=selected_variant,
            )

        except KeyError as exc:
            raise HTTPException(
                status_code=500,
                detail=(
                    f"A/B variant '{selected_variant}' "
                    f"is configured but not loaded: {exc}"
                ),
            ) from exc

        # ----------------------------------------------------
        # Execute selected version
        #
        # ModelManager handles A/B metrics because we pass
        # variant=selected_variant.
        # ----------------------------------------------------

        try:
            result = model_manager.predict_version(
                model_name=model_name,
                version=selected_variant,
                payload=request.payload,
                variant=selected_variant,
                quality_score=request.quality_score,
            )

        except KeyError as exc:
            raise HTTPException(
                status_code=404,
                detail=str(exc),
            ) from exc

        except ValueError as exc:
            # Client/model input validation errors are 422.
            # ModelManager's metric recording is not reached
            # for this HTTP-level validation path.
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

        except HTTPException:
            raise

        except Exception as exc:
            # Genuine model execution failure.
            raise HTTPException(
                status_code=500,
                detail=(
                    f"A/B prediction failed for "
                    f"variant '{selected_variant}': "
                    f"{exc}"
                ),
            ) from exc

        # ----------------------------------------------------
        # Return A/B information
        # ----------------------------------------------------

        return {
            "model": model_name,
            "request_id": request_id,
            "bucket": bucket,
            "variant": selected_variant,
            "variant_a": experiment.variant_a,
            "variant_b": experiment.variant_b,
            "traffic_percentage": (
                experiment.traffic_percentage
            ),
            "prediction": result,
        }

    # ========================================================
    # A/B Summary
    # ========================================================

    @router.get(
        "/{model_name}/ab-test"
    )
    def ab_test_summary(
        model_name: str,
    ) -> Dict[str, Any]:
        """
        Return A/B metrics and statistical verdict.

        The configured ABExperiment determines which actual
        model version is variant A and which is variant B.

        We do NOT rely on dictionary insertion order.
        """

        # ----------------------------------------------------
        # Get experiment configuration
        # ----------------------------------------------------

        experiment = _get_ab_experiment(
            model_manager,
            model_name,
        )

        # ----------------------------------------------------
        # Get collected metrics
        # ----------------------------------------------------

        try:
            metrics = model_manager.get_ab_metrics(
                model_name
            )

        except KeyError as exc:
            raise HTTPException(
                status_code=404,
                detail=str(exc),
            ) from exc

        # ----------------------------------------------------
        # Explicit configured variant order
        # ----------------------------------------------------

        variant_a_name = (
            experiment.variant_a
        )

        variant_b_name = (
            experiment.variant_b
        )

        variant_a_metrics = metrics.get(
            variant_a_name,
            _empty_variant_metrics(),
        )

        variant_b_metrics = metrics.get(
            variant_b_name,
            _empty_variant_metrics(),
        )

        # ----------------------------------------------------
        # Statistical comparison
        # ----------------------------------------------------

        verdict = compare_variants(
            metrics_a=variant_a_metrics,
            metrics_b=variant_b_metrics,
        )

        # ----------------------------------------------------
        # Map generic labels to actual model versions
        #
        # Example:
        #
        # variant_a = "v1"
        # variant_b = "v2"
        #
        # compare_variants() says:
        # winner = "variant_b"
        #
        # API returns:
        # winner = "v2"
        # ----------------------------------------------------

        generic_winner = verdict.get(
            "winner"
        )

        generic_loser = verdict.get(
            "loser"
        )

        if generic_winner == "variant_a":
            actual_winner = variant_a_name

        elif generic_winner == "variant_b":
            actual_winner = variant_b_name

        else:
            actual_winner = None

        if generic_loser == "variant_a":
            actual_loser = variant_a_name

        elif generic_loser == "variant_b":
            actual_loser = variant_b_name

        else:
            actual_loser = None

        verdict = {
            **verdict,
            "winner": actual_winner,
            "loser": actual_loser,
            "variant_a": variant_a_name,
            "variant_b": variant_b_name,
        }

        # ----------------------------------------------------
        # Return response
        # ----------------------------------------------------

        return {
            "model": model_name,
            "experiment": {
                "model_name": experiment.model_name,
                "variant_a": variant_a_name,
                "variant_b": variant_b_name,
                "traffic_percentage": (
                    experiment.traffic_percentage
                ),
            },
            "metrics": {
                variant_a_name: variant_a_metrics,
                variant_b_name: variant_b_metrics,
            },
            "verdict": verdict,
        }

    return router