"""
API router for unified multi-model serving.
"""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from src.model_manager import ModelManager
from src.schemas import ModelPredictionRequest
from src.ab_testing import (
    ABExperiment,
    assign_variant,
    compare_variants,
)


def create_router(
    model_manager: ModelManager,
) -> APIRouter:

    router = APIRouter(
        prefix="/models",
        tags=["Multi-Model Serving"],
    )

    # ==========================================================
    # GET /models
    # ==========================================================

    @router.get("")
    def list_models() -> Dict[str, Any]:

        return {
            "models": model_manager.list_models()
        }

    # ==========================================================
    # GET /models/{model_name}
    # ==========================================================

    @router.get("/{model_name}")
    def get_model(
        model_name: str,
    ) -> Dict[str, Any]:

        try:

            return model_manager.get_model_info(
                model_name
            )

        except KeyError as exc:

            raise HTTPException(
                status_code=404,
                detail=str(exc),
            )

    # ==========================================================
    # POST /models/{model_name}/predict
    # ==========================================================

    @router.post("/{model_name}/predict")
    def predict(
        model_name: str,
        request: ModelPredictionRequest,
    ) -> Dict[str, Any]:

        try:

            return model_manager.predict(
                model_name=model_name,
                payload=request.payload,
            )

        except KeyError as exc:

            raise HTTPException(
                status_code=404,
                detail=str(exc),
            )

        except ValueError as exc:

            raise HTTPException(
                status_code=422,
                detail=str(exc),
            )

    # ==========================================================
    # GET /models/{model_name}/ab-test
    # ==========================================================

    @router.get("/{model_name}/ab-test")
    def ab_test_summary(
        model_name: str,
    ) -> Dict[str, Any]:

        try:

            metrics = model_manager.get_ab_metrics(
                model_name
            )

        except KeyError as exc:

            raise HTTPException(
                status_code=404,
                detail=str(exc),
            )

        variants = list(metrics.keys())

        if len(variants) < 2:

            return {
                "model": model_name,
                "metrics": metrics,
                "verdict": {
                    "verdict": "inconclusive",
                    "reason": (
                        "At least two variants "
                        "are required."
                    ),
                },
            }

        variant_a = metrics[variants[0]]
        variant_b = metrics[variants[1]]

        verdict = compare_variants(
            variant_a,
            variant_b,
        )

        return {
            "model": model_name,
            "metrics": metrics,
            "verdict": verdict,
        }

    return router