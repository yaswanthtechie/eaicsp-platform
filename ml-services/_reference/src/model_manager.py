"""
Central model manager for the unified multi-model serving platform.
"""

import time
from typing import Any, Dict

from src.registry import model_exists
from src.adapters.base import BaseModelAdapter
from src.ab_testing import ABMetrics


class ModelManager:
    """
    Manages all models exposed by the unified serving layer.

    Supports:
    - Normal production prediction
    - Multiple model versions
    - A/B testing between versions
    - Per-variant metrics
    """

    def __init__(self) -> None:

        # Existing production/default adapters
        self.adapters: Dict[str, BaseModelAdapter] = {}

        # Versioned adapters:
        # {
        #     "forecast": {
        #         "v1": adapter,
        #         "v2": adapter,
        #     }
        # }
        self.versioned_adapters: Dict[
            str,
            Dict[str, BaseModelAdapter],
        ] = {}

        # A/B metrics per model
        self.ab_metrics: Dict[str, ABMetrics] = {}

    # ==========================================================
    # Registration
    # ==========================================================

    def register(
        self,
        adapter: BaseModelAdapter,
    ) -> None:
        """
        Register a model adapter as the default/production adapter.
        """

        model_name = adapter.model_name.strip().lower()

        if not model_name:
            raise ValueError(
                "Adapter model_name cannot be empty."
            )

        if not model_exists(model_name):
            raise ValueError(
                f"Model '{model_name}' is not present "
                "in the model registry."
            )

        self.adapters[model_name] = adapter

        self.versioned_adapters.setdefault(
            model_name,
            {},
        )

        self.versioned_adapters[
            model_name
        ][adapter.model_version] = adapter

        self.ab_metrics.setdefault(
            model_name,
            ABMetrics(),
        )

    def register_version(
        self,
        adapter: BaseModelAdapter,
    ) -> None:
        """
        Register an additional model version.

        Example:
            forecast v1
            forecast v2
        """

        model_name = adapter.model_name.strip().lower()

        if not model_name:
            raise ValueError(
                "Adapter model_name cannot be empty."
            )

        if not model_exists(model_name):
            raise ValueError(
                f"Model '{model_name}' is not present "
                "in the model registry."
            )

        if not adapter.model_version.strip():
            raise ValueError(
                "Adapter model_version cannot be empty."
            )

        self.versioned_adapters.setdefault(
            model_name,
            {},
        )

        self.versioned_adapters[
            model_name
        ][adapter.model_version] = adapter

        self.ab_metrics.setdefault(
            model_name,
            ABMetrics(),
        )

    # ==========================================================
    # Model lookup
    # ==========================================================

    def get_adapter(
        self,
        model_name: str,
    ) -> BaseModelAdapter:

        model_name = model_name.strip().lower()

        if model_name not in self.adapters:
            raise KeyError(
                f"Model '{model_name}' is not loaded."
            )

        return self.adapters[model_name]

    def get_version_adapter(
        self,
        model_name: str,
        version: str,
    ) -> BaseModelAdapter:

        model_name = model_name.strip().lower()

        if model_name not in self.versioned_adapters:
            raise KeyError(
                f"Model '{model_name}' is not loaded."
            )

        versions = self.versioned_adapters[
            model_name
        ]

        if version not in versions:
            raise KeyError(
                f"Model '{model_name}' version "
                f"'{version}' is not loaded."
            )

        return versions[version]

    # ==========================================================
    # Normal prediction
    # ==========================================================

    def predict(
        self,
        model_name: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:

        adapter = self.get_adapter(model_name)

        return self._predict_with_adapter(
            adapter,
            payload,
        )

    # ==========================================================
    # Version-specific prediction
    # ==========================================================

    def predict_version(
        self,
        model_name: str,
        version: str,
        payload: Dict[str, Any],
        variant: str | None = None,
    ) -> Dict[str, Any]:

        adapter = self.get_version_adapter(
            model_name,
            version,
        )

        start_time = time.perf_counter()

        try:

            result = adapter.predict(payload)

            success = True

        except Exception:

            success = False

            latency_ms = (
                time.perf_counter() - start_time
            ) * 1000.0

            if variant is not None:
                self.ab_metrics[
                    model_name
                ].record(
                    variant=variant,
                    latency_ms=latency_ms,
                    success=False,
                )

            raise

        latency_ms = (
            time.perf_counter() - start_time
        ) * 1000.0

        if variant is not None:
            self.ab_metrics[
                model_name
            ].record(
                variant=variant,
                latency_ms=latency_ms,
                success=success,
            )

        return {
            "model": adapter.model_name,
            "model_version": adapter.model_version,
            "prediction": result.get(
                "prediction",
                result,
            ),
            "confidence": result.get(
                "confidence",
            ),
            "latency_ms": round(
                latency_ms,
                3,
            ),
        }

    # ==========================================================
    # Internal prediction helper
    # ==========================================================

    def _predict_with_adapter(
        self,
        adapter: BaseModelAdapter,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:

        start_time = time.perf_counter()

        result = adapter.predict(payload)

        latency_ms = (
            time.perf_counter() - start_time
        ) * 1000.0

        return {
            "model": adapter.model_name,
            "model_version": adapter.model_version,
            "prediction": result.get(
                "prediction",
                result,
            ),
            "confidence": result.get(
                "confidence",
            ),
            "latency_ms": round(
                latency_ms,
                3,
            ),
        }

    # ==========================================================
    # A/B metrics
    # ==========================================================

    def get_ab_metrics(
        self,
        model_name: str,
    ) -> Dict[str, Any]:

        model_name = model_name.strip().lower()

        if model_name not in self.ab_metrics:
            raise KeyError(
                f"No A/B metrics found for model "
                f"'{model_name}'."
            )

        return self.ab_metrics[
            model_name
        ].summary()

    # ==========================================================
    # Model metadata
    # ==========================================================

    def get_model_info(
        self,
        model_name: str,
    ) -> Dict[str, Any]:

        adapter = self.get_adapter(model_name)

        return {
            "model": adapter.model_name,
            "production_version": (
                adapter.model_version
            ),
            "status": "ready",
        }

    # ==========================================================
    # All models
    # ==========================================================

    def list_models(self) -> list[Dict[str, Any]]:

        return [
            self.get_model_info(model_name)
            for model_name in sorted(
                self.adapters.keys()
            )
        ]

    # ==========================================================
    # Health
    # ==========================================================

    def health(self) -> Dict[str, Any]:

        model_status = {}

        for model_name, adapter in self.adapters.items():

            model_status[model_name] = {
                "status": "ready",
                "version": adapter.model_version,
            }

        return {
            "status": "healthy",
            "models": model_status,
        }