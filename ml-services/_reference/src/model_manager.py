"""
Central model manager for the unified multi-model serving platform.

Responsibilities:
- Register production model adapters
- Register multiple model versions
- Run production predictions
- Run version-specific predictions for A/B testing
- Store A/B experiment configuration
- Collect per-variant A/B metrics
- Provide model health and information
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from src.ab_testing import ABMetrics
from src.adapters.base import BaseModelAdapter
from src.experiment import ABExperiment
from src.registry import model_exists


class ModelManager:
    """
    Manages all models exposed by the unified serving layer.

    Supports:
    - Normal production prediction
    - Multiple model versions
    - A/B testing between versions
    - Per-variant quality metrics
    - A/B experiment configuration
    """

    def __init__(self) -> None:
        self.adapters: Dict[str, BaseModelAdapter] = {}

        self.versioned_adapters: Dict[
            str,
            Dict[str, BaseModelAdapter],
        ] = {}

        self.ab_metrics: Dict[
            str,
            ABMetrics,
        ] = {}

        self.ab_experiments: Dict[
            str,
            ABExperiment,
        ] = {}

    # ========================================================
    # Model Registration
    # ========================================================

    def register(
        self,
        adapter: BaseModelAdapter,
    ) -> None:
        """
        Register an adapter as the current production version.

        The adapter is also registered inside the version map.
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

        This does NOT change the production version.
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

    # ========================================================
    # A/B Experiment Registration
    # ========================================================

    def register_ab_experiment(
        self,
        experiment: ABExperiment,
    ) -> None:
        """
        Register an A/B experiment for a model.

        variant_a:
            Control / production version.

        variant_b:
            Challenger / staging version.

        Both configured versions must already be loaded.
        """

        if not isinstance(
            experiment,
            ABExperiment,
        ):
            raise TypeError(
                "experiment must be an ABExperiment instance."
            )

        model_name = (
            experiment.model_name
            .strip()
            .lower()
        )

        if not model_name:
            raise ValueError(
                "Experiment model_name cannot be empty."
            )

        if model_name not in self.versioned_adapters:
            raise KeyError(
                f"Model '{model_name}' is not registered."
            )

        if (
            experiment.variant_a
            not in self.versioned_adapters[model_name]
        ):
            raise KeyError(
                f"Model '{model_name}' version "
                f"'{experiment.variant_a}' is not loaded."
            )

        if (
            experiment.variant_b
            not in self.versioned_adapters[model_name]
        ):
            raise KeyError(
                f"Model '{model_name}' version "
                f"'{experiment.variant_b}' is not loaded."
            )

        self.ab_experiments[
            model_name
        ] = experiment

    def get_ab_experiment(
        self,
        model_name: str,
    ) -> ABExperiment:
        """Return the configured A/B experiment for a model."""

        model_name = model_name.strip().lower()

        if model_name not in self.ab_experiments:
            raise KeyError(
                f"No A/B experiment configured for "
                f"model '{model_name}'."
            )

        return self.ab_experiments[
            model_name
        ]

    # ========================================================
    # Adapter Access
    # ========================================================

    def get_adapter(
        self,
        model_name: str,
    ) -> BaseModelAdapter:
        """Return the current production adapter."""

        model_name = model_name.strip().lower()

        if model_name not in self.adapters:
            raise KeyError(
                f"Model '{model_name}' is not loaded."
            )

        return self.adapters[
            model_name
        ]

    def get_version_adapter(
        self,
        model_name: str,
        version: str,
    ) -> BaseModelAdapter:
        """Return a specific version of a model."""

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

        return versions[
            version
        ]

    # ========================================================
    # Production Prediction
    # ========================================================

    def predict(
        self,
        model_name: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run prediction using the current production adapter."""

        adapter = self.get_adapter(
            model_name
        )

        return self._predict_with_adapter(
            adapter,
            payload,
        )

    # ========================================================
    # Version-Specific Prediction
    # ========================================================

    def predict_version(
        self,
        model_name: str,
        version: str,
        payload: Dict[str, Any],
        variant: Optional[str] = None,
        quality_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Run prediction using a specific model version.

        Parameters
        ----------
        model_name:
            Registered model name.

        version:
            Specific model version.

        payload:
            Model input.

        variant:
            A/B variant name. If provided, runtime metrics
            are recorded against this variant.

        quality_score:
            Optional externally calculated quality score.

            This should represent the actual model-quality
            measurement for the prediction, rather than
            whether the model executed successfully.

        Notes
        -----
        Execution failure and model-quality failure are
        intentionally kept separate.
        """

        adapter = self.get_version_adapter(
            model_name,
            version,
        )

        start_time = time.perf_counter()

        try:
            result = adapter.predict(
                payload
            )

        except Exception:
            latency_ms = (
                time.perf_counter()
                - start_time
            ) * 1000.0

            # Record execution failure only.
            #
            # Do NOT convert this into a quality score.
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
            time.perf_counter()
            - start_time
        ) * 1000.0

        # ----------------------------------------------------
        # Record successful model execution
        # ----------------------------------------------------
        #
        # If a genuine quality score is available, store it.
        # Otherwise we only record execution information.
        #
        if variant is not None:
            self.ab_metrics[
                model_name
            ].record(
                variant=variant,
                latency_ms=latency_ms,
                success=True,
                quality_score=quality_score,
            )

        return {
            "model": adapter.model_name,
            "model_version": adapter.model_version,
            "prediction": result.get(
                "prediction",
                result,
            ),
            "confidence": result.get(
                "confidence"
            ),
            "quality_score": quality_score,
            "latency_ms": round(
                latency_ms,
                3,
            ),
        }

    # ========================================================
    # Internal Prediction Helper
    # ========================================================

    def _predict_with_adapter(
        self,
        adapter: BaseModelAdapter,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute an adapter and return a standardized response."""

        start_time = time.perf_counter()

        result = adapter.predict(
            payload
        )

        latency_ms = (
            time.perf_counter()
            - start_time
        ) * 1000.0

        return {
            "model": adapter.model_name,
            "model_version": adapter.model_version,
            "prediction": result.get(
                "prediction",
                result,
            ),
            "confidence": result.get(
                "confidence"
            ),
            "latency_ms": round(
                latency_ms,
                3,
            ),
        }

    # ========================================================
    # A/B Metrics
    # ========================================================

    def get_ab_metrics(
        self,
        model_name: str,
    ) -> Dict[str, Any]:
        """Return A/B metrics for a model."""

        model_name = model_name.strip().lower()

        if model_name not in self.ab_metrics:
            raise KeyError(
                f"No A/B metrics found for "
                f"model '{model_name}'."
            )

        return self.ab_metrics[
            model_name
        ].summary()

    # ========================================================
    # Model Information
    # ========================================================

    def get_model_info(
        self,
        model_name: str,
    ) -> Dict[str, Any]:
        """Return production model information."""

        adapter = self.get_adapter(
            model_name
        )

        return {
            "model": adapter.model_name,
            "production_version": adapter.model_version,
            "status": "ready",
        }

    # ========================================================
    # List Models
    # ========================================================

    def list_models(
        self,
    ) -> list[Dict[str, Any]]:
        """Return all registered production models."""

        return [
            self.get_model_info(
                model_name
            )
            for model_name in sorted(
                self.adapters.keys()
            )
        ]

    # ========================================================
    # Health
    # ========================================================

    def health(
        self,
    ) -> Dict[str, Any]:
        """Return health status for all loaded production models."""

        model_status = {}

        for (
            model_name,
            adapter,
        ) in self.adapters.items():

            model_status[
                model_name
            ] = {
                "status": "ready",
                "version": adapter.model_version,
            }

        return {
            "status": "healthy",
            "models": model_status,
        }