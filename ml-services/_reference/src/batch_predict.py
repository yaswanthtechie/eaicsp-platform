"""
Batch prediction service.

Runs predictions for multiple models from a single batch request.

Predictions for independent models are executed concurrently.

Example batch:

{
    "requests": [
        {
            "model_name": "forecast",
            "features": {
                "history": [100, 110, 120, 130],
                "horizon": 3
            }
        },
        {
            "model_name": "eta",
            "features": {
                "origin": "Chennai",
                "destination": "Bangalore",
                "carrier": "BlueDart",
                "weight_kg": 5.0
            }
        }
    ]
}
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from src.resource_monitor import ResourceMonitor


@dataclass
class BatchPredictionResult:
    model_name: str
    success: bool
    prediction: Any = None
    error: str | None = None
    latency_ms: float = 0.0


class BatchPredictionService:
    """
    Execute multiple model predictions as one batch operation.

    Independent model predictions are executed concurrently.

    The service intentionally keeps model execution behind the
    existing model manager so model loading/versioning remains
    centralized.
    """

    def __init__(self, model_manager):
        self.model_manager = model_manager
        self.resource_monitor = ResourceMonitor()

    def _predict_one(
        self,
        model_name: str,
        features: dict[str, Any],
    ) -> BatchPredictionResult:
        """
        Execute one model prediction.

        ModelManager expects the model input using the
        `payload` argument. The external batch API continues
        to expose this input as `features`.
        """

        prediction_started = time.perf_counter()

        try:
            prediction = self.model_manager.predict(
                model_name=model_name,
                payload=features,
            )

            prediction_latency = (
                time.perf_counter() - prediction_started
            ) * 1000

            return BatchPredictionResult(
                model_name=model_name,
                success=True,
                prediction=prediction,
                latency_ms=round(
                    prediction_latency,
                    3,
                ),
            )

        except Exception as exc:
            prediction_latency = (
                time.perf_counter() - prediction_started
            ) * 1000

            return BatchPredictionResult(
                model_name=model_name,
                success=False,
                error=str(exc),
                latency_ms=round(
                    prediction_latency,
                    3,
                ),
            )

    def predict(
        self,
        requests: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Run multiple model predictions concurrently.

        Invalid requests are reported as individual failures
        instead of failing the complete batch.
        """

        if not requests:
            raise ValueError(
                "Batch request cannot be empty"
            )

        started_at = time.perf_counter()

        results: list[BatchPredictionResult | None] = [
            None
        ] * len(requests)

        valid_requests: list[
            tuple[int, str, dict[str, Any]]
        ] = []

        # ----------------------------------------------------
        # Validate requests first
        # ----------------------------------------------------

        for index, request in enumerate(requests):
            model_name = request.get("model_name")
            features = request.get("features")

            if not model_name:
                results[index] = BatchPredictionResult(
                    model_name="unknown",
                    success=False,
                    error="model_name is required",
                )
                continue

            if features is None:
                results[index] = BatchPredictionResult(
                    model_name=model_name,
                    success=False,
                    error="features are required",
                )
                continue

            if not isinstance(features, dict):
                results[index] = BatchPredictionResult(
                    model_name=model_name,
                    success=False,
                    error="features must be an object",
                )
                continue

            valid_requests.append(
                (
                    index,
                    model_name,
                    features,
                )
            )

        # ----------------------------------------------------
        # Execute independent predictions concurrently
        # ----------------------------------------------------

        if valid_requests:
            max_workers = min(
                len(valid_requests),
                8,
            )

            with ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix="batch-predict",
            ) as executor:

                future_to_index = {
                    executor.submit(
                        self._predict_one,
                        model_name,
                        features,
                    ): index
                    for (
                        index,
                        model_name,
                        features,
                    ) in valid_requests
                }

                for future in as_completed(
                    future_to_index
                ):
                    index = future_to_index[future]

                    try:
                        results[index] = future.result()

                    except Exception as exc:
                        # Defensive fallback. _predict_one already
                        # catches model errors, but this protects
                        # the batch operation from unexpected
                        # worker failures.
                        _, model_name, _ = next(
                            item
                            for item in valid_requests
                            if item[0] == index
                        )

                        results[index] = BatchPredictionResult(
                            model_name=model_name,
                            success=False,
                            error=str(exc),
                        )

        # ----------------------------------------------------
        # Remove type-check ambiguity after validation
        # ----------------------------------------------------

        final_results = [
            result
            for result in results
            if result is not None
        ]

        successful = sum(
            1
            for result in final_results
            if result.success
        )

        # ----------------------------------------------------
        # Resource metrics
        # ----------------------------------------------------

        model_names = {
            request.get("model_name")
            for request in requests
            if request.get("model_name")
        }

        metrics = self.resource_monitor.measure_batch(
            batch_size=len(requests),
            model_count=len(model_names),
            total_predictions=len(requests),
            started_at=started_at,
        )

        # ----------------------------------------------------
        # Standardized response
        # ----------------------------------------------------

        return {
            "results": [
                {
                    "model_name": result.model_name,
                    "success": result.success,
                    "prediction": result.prediction,
                    "error": result.error,
                    "latency_ms": result.latency_ms,
                }
                for result in final_results
            ],
            "summary": {
                "batch_size": len(requests),
                "successful_predictions": successful,
                "failed_predictions": (
                    len(requests) - successful
                ),
                "model_count": metrics.model_count,
            },
            "resource_metrics": metrics.to_dict(),
        }