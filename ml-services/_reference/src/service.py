"""
BentoML service for Iris classification and unified multi-model serving.

R4/R5 Features:
- Iris prediction
- Batch prediction
- Health check
- Runtime metrics
- Per-model monitoring
- Drift detection
- Automated retraining
- Model promotion
- Model rollback
- Safe retraining scheduler

Milestone 1:
- Unified multi-model serving
- Forecast model
- ETA model
- Anomaly model
- Supplier risk model
- Central model manager
- Model versioning

Milestone 2:
- Deterministic A/B testing
- v1/v2 model routing
- Per-variant metrics
- Statistical comparison

Milestone 3:
- Multi-model retraining orchestration
- Per-model drift decision
- Multi-model retraining endpoint
- Single-model retraining endpoint
- Safe orchestration integration

Milestone 4:
- MLOps dashboard
- Unified model health visibility
- Production model versions
- Request volume
- Success rate
- Average latency
- A/B testing metrics
- Dashboard auto-refresh
"""

import logging
import os
import time
import uuid

import bentoml
import numpy as np

from fastapi import FastAPI

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)

from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split


# ==========================================================
# Unified Multi-Model Serving
# ==========================================================

from src.model_manager import ModelManager

from src.router import create_router

from src.adapters import (
    ForecastAdapter,
    ETAAdapter,
    AnomalyAdapter,
    RiskAdapter,
)


# ==========================================================
# R5 Monitoring
# ==========================================================

from src.monitoring import (
    get_summary,
    log_prediction,
    get_recent_inputs,
)


# ==========================================================
# Iris Prediction
# ==========================================================

from src.predict import load_model


# ==========================================================
# Iris Canary
# ==========================================================

from src.canary import (
    load_canary_models,
    select_model,
)


# ==========================================================
# R5 Retraining
# ==========================================================

from src.retraining import (
    check_retraining_needed,
    automated_retrain,
)


# ==========================================================
# R5 Scheduler
# ==========================================================

from src.scheduler import RetrainingScheduler


# ==========================================================
# R5 Rollback
# ==========================================================

from src.rollback import should_rollback


# ==========================================================
# MLflow Utilities
# ==========================================================

from src.mlflow_utils import (
    assign_staging,
    promote_model,
    rollback_model,
)


# ==========================================================
# Milestone 3 Multi-Model Retraining
# ==========================================================

from src.orchestrator import (
    MultiModelRetrainingOrchestrator,
)

from src.retraining_adapters import (
    check_drift,
)


# ==========================================================
# Milestone 4 MLOps Dashboard
# ==========================================================

from src.dashboard import (
    create_dashboard_router,
)


# ==========================================================
# Configuration
# ==========================================================

from src.config import (
    MODEL_NAME,
    RETRAINING_INTERVAL_SECONDS,
    MIN_RETRAINING_SAMPLES,
    MONITORING_INPUT_LIMIT,
    ENABLE_RETRAINING_SCHEDULER,
    TEST_SIZE,
    RANDOM_STATE,
    PROMOTION_ACCURACY_THRESHOLD,
    MULTIMODEL_DRIFT_THRESHOLD,
    should_promote,
)


# ==========================================================
# Logging
# ==========================================================

logging.basicConfig(
    level=logging.INFO
)

logger = logging.getLogger(__name__)


# ==========================================================
# Iris Target Names
# ==========================================================

TARGET_NAMES = load_iris().target_names


# ==========================================================
# Iris Request Models
# ==========================================================


class IrisRequest(BaseModel):
    """
    Single Iris prediction request.
    """

    features: list[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Exactly four Iris features",
    )


class IrisBatchRequest(BaseModel):
    """
    Batch Iris prediction request.
    """

    features: list[list[float]] = Field(
        ...,
        min_length=1,
        description="List of Iris feature vectors",
    )

    @field_validator("features")
    @classmethod
    def validate_features(cls, value):
        for row in value:
            if len(row) != 4:
                raise ValueError(
                    "Each sample must contain exactly 4 features."
                )

        return value


# ==========================================================
# Retraining Check Request
# ==========================================================


class RetrainingCheckRequest(BaseModel):
    """
    Request for checking input feature drift.
    """

    recent_inputs: list[list[float]] = Field(
        ...,
        min_length=1,
        description="Recent prediction input samples",
    )

    @field_validator("recent_inputs")
    @classmethod
    def validate_recent_inputs(cls, value):
        for row in value:
            if len(row) != 4:
                raise ValueError(
                    "Each sample must contain exactly 4 features."
                )

        return value


# ==========================================================
# Rollback Request
# ==========================================================


class RollbackRequest(BaseModel):
    """
    Request used to simulate production performance
    of a newly promoted model.
    """

    new_model_accuracy: float = Field(
        ...,
        ge=0.0,
        le=1.0,
    )

    previous_model_accuracy: float = Field(
        ...,
        ge=0.0,
        le=1.0,
    )


# ==========================================================
# Iris Prediction Response
# ==========================================================


class PredictionResponse(BaseModel):
    """
    Iris prediction response.
    """

    prediction: str
    confidence: float
    model_version: str
    latency_ms: float
    probabilities: dict[str, float]


# ==========================================================
# Unified Multi-Model Manager
# ==========================================================

MULTI_MODEL_MANAGER = ModelManager()


# ==========================================================
# Register Production v1 Adapters
# ==========================================================

MULTI_MODEL_MANAGER.register(
    ForecastAdapter()
)

MULTI_MODEL_MANAGER.register(
    ETAAdapter()
)

MULTI_MODEL_MANAGER.register(
    AnomalyAdapter()
)

MULTI_MODEL_MANAGER.register(
    RiskAdapter()
)


# ==========================================================
# Register v2 Adapters for A/B Testing
# ==========================================================
#
# v1 -> production/default
# v2 -> A/B test candidate
#
# IMPORTANT:
# The current v2 adapters use the same backend/model
# implementation as v1. This validates the A/B infrastructure.
# A genuinely different trained model can be plugged into the
# v2 adapter later.
# ==========================================================


forecast_v2 = ForecastAdapter()
forecast_v2.model_version = "v2"

eta_v2 = ETAAdapter()
eta_v2.model_version = "v2"

anomaly_v2 = AnomalyAdapter()
anomaly_v2.model_version = "v2"

risk_v2 = RiskAdapter()
risk_v2.model_version = "v2"


MULTI_MODEL_MANAGER.register_version(
    forecast_v2
)

MULTI_MODEL_MANAGER.register_version(
    eta_v2
)

MULTI_MODEL_MANAGER.register_version(
    anomaly_v2
)

MULTI_MODEL_MANAGER.register_version(
    risk_v2
)


# ==========================================================
# FastAPI Multi-Model Application
# ==========================================================

multi_model_app = FastAPI(
    title="Unified Multi-Model Serving API",
    version="2.0.0",
    description=(
        "Unified serving API for forecast, ETA, "
        "anomaly detection and supplier risk models."
    ),
)


# ==========================================================
# Unified Multi-Model API Router
# ==========================================================

multi_model_app.include_router(
    create_router(
        MULTI_MODEL_MANAGER
    )
)


# ==========================================================
# Milestone 4 MLOps Dashboard Router
# ==========================================================

multi_model_app.include_router(
    create_dashboard_router(
        model_manager=MULTI_MODEL_MANAGER,
    )
)


# ==========================================================
# BentoML Service
# ==========================================================


@bentoml.service(name="iris_service")
@bentoml.asgi_app(
    multi_model_app,
    path="/",
)
class IrisService:

    # ======================================================
    # Initialization
    # ======================================================

    def __init__(self):

        # --------------------------------------------------
        # Load Production Iris Model
        # --------------------------------------------------

        self.model, self.model_version = (
            load_model()
        )

        # --------------------------------------------------
        # Load Canary Models
        # --------------------------------------------------

        self.canary_models = (
            load_canary_models()
        )

        # --------------------------------------------------
        # Prediction Metrics
        # --------------------------------------------------

        self.total_predictions = 0

        # Single prediction metrics

        self.total_single_predictions = 0

        self.total_single_latency = 0.0

        # Batch prediction metrics

        self.total_batches = 0

        self.total_batch_latency = 0.0

        # Errors

        self.error_count = 0

        # --------------------------------------------------
        # Milestone 3 Multi-Model Retraining
        # --------------------------------------------------

        self.multimodel_orchestrator = (
            self._create_multimodel_orchestrator()
        )

        # --------------------------------------------------
        # R5 Retraining Scheduler
        # --------------------------------------------------

        self.retraining_scheduler = None

        # --------------------------------------------------
        # Scheduler environment override
        # --------------------------------------------------
        #
        # Safe default remains:
        #
        # ENABLE_RETRAINING_SCHEDULER = False
        #
        # A live R5 demo can explicitly enable it:
        #
        # ENABLE_RETRAINING_SCHEDULER=true
        #
        # --------------------------------------------------

        scheduler_env = os.getenv(
            "ENABLE_RETRAINING_SCHEDULER"
        )

        if scheduler_env is None:

            scheduler_enabled = (
                ENABLE_RETRAINING_SCHEDULER
            )

        else:

            scheduler_enabled = (
                scheduler_env.strip().lower()
                == "true"
            )

        # --------------------------------------------------
        # Scheduler Interval environment override
        # --------------------------------------------------

        interval_env = os.getenv(
            "RETRAINING_INTERVAL_SECONDS"
        )

        if interval_env is None:

            scheduler_interval = (
                RETRAINING_INTERVAL_SECONDS
            )

        else:

            try:

                scheduler_interval = int(
                    interval_env
                )

            except ValueError:

                logger.warning(
                    "Invalid RETRAINING_INTERVAL_SECONDS=%s. "
                    "Using configured value=%s.",
                    interval_env,
                    RETRAINING_INTERVAL_SECONDS,
                )

                scheduler_interval = (
                    RETRAINING_INTERVAL_SECONDS
                )

        # --------------------------------------------------
        # Start scheduler only when explicitly enabled
        # --------------------------------------------------

        if scheduler_enabled:

            self.retraining_scheduler = (
                RetrainingScheduler(
                    check_function=(
                        self._scheduled_retraining_check
                    ),
                    interval_seconds=(
                        scheduler_interval
                    ),
                )
            )

            self.retraining_scheduler.start()

            logger.info(
                "R5 retraining scheduler started "
                "(interval=%s seconds)",
                scheduler_interval,
            )

        else:

            logger.info(
                "R5 retraining scheduler disabled"
            )

        # --------------------------------------------------
        # Logging
        # --------------------------------------------------

        logger.info(
            "Loaded production model version: %s",
            self.model_version,
        )

        logger.info(
            "Unified multi-model serving enabled: %s",
            list(
                MULTI_MODEL_MANAGER.adapters.keys()
            ),
        )

        logger.info(
            "A/B testing versions registered: %s",
            {
                model_name: list(
                    versions.keys()
                )
                for model_name, versions
                in MULTI_MODEL_MANAGER.versioned_adapters.items()
            },
        )

        logger.info(
            "Milestone 3 multi-model retraining "
            "orchestrator initialized for: %s",
            [
                "forecast",
                "eta",
                "anomaly",
                "risk",
            ],
        )

        logger.info(
            "Milestone 4 MLOps dashboard available at "
            "/mlops/dashboard"
        )

    # ======================================================
    # Milestone 3 Orchestrator Creation
    # ======================================================

    def _create_multimodel_orchestrator(self):
        """
        Create the Milestone 3 multi-model retraining
        orchestrator.

        The actual model-specific retraining pipelines
        are isolated behind callbacks.

        The orchestration layer is safe by default.
        """

        model_names = (
            "forecast",
            "eta",
            "anomaly",
            "risk",
        )

        models = {}

        for model_name in model_names:

            # --------------------------------------------------
            # Production version
            # --------------------------------------------------

            def get_version(name=model_name):

                adapter = (
                    MULTI_MODEL_MANAGER.get_adapter(
                        name
                    )
                )

                return adapter.model_version

            # --------------------------------------------------
            # Drift check
            # --------------------------------------------------

            def check_model_drift(
                name=model_name,
            ):
                """
                Perform the Milestone 3 drift decision.

                The actual model-specific monitoring and
                retraining pipelines can provide the real
                drift signal through this callback.
                """

                return check_drift(
                    model_name=name,
                    drift_score=0.0,
                    threshold=(
                        MULTIMODEL_DRIFT_THRESHOLD
                    ),
                )

            # --------------------------------------------------
            # Retraining callback
            # --------------------------------------------------

            def retrain(
                name=model_name,
            ):
                """
                Placeholder safety callback.

                Real model-specific retraining is connected
                independently by the corresponding pipeline.
                """

                raise RuntimeError(
                    f"Real retraining pipeline for "
                    f"'{name}' is not connected yet."
                )

            # --------------------------------------------------
            # Production evaluation callback
            # --------------------------------------------------

            def evaluate_production(
                name=model_name,
            ):
                """
                Placeholder safety callback.
                """

                raise RuntimeError(
                    f"Production evaluation for "
                    f"'{name}' is not connected yet."
                )

            # --------------------------------------------------
            # Promotion callback
            # --------------------------------------------------

            def promote(
                version,
                name=model_name,
            ):
                """
                Placeholder safety callback.
                """

                raise RuntimeError(
                    f"Promotion pipeline for "
                    f"'{name}' is not connected yet."
                )

            # --------------------------------------------------
            # Register model configuration
            # --------------------------------------------------

            models[model_name] = {
                "get_version": get_version,
                "check_drift": check_model_drift,
                "retrain": retrain,
                "evaluate_production": (
                    evaluate_production
                ),
                "promote": promote,
            }

        return MultiModelRetrainingOrchestrator(
            models=models
        )

    # ======================================================
    # Milestone 3 Orchestrator Run Helper
    # ======================================================

    def _run_multimodel_retraining(self):

        """
        Execute one Milestone 3 multi-model
        orchestration cycle.
        """

        logger.warning(
            "Milestone 3 multi-model retraining "
            "cycle started"
        )

        result = (
            self.multimodel_orchestrator.run_all()
        )

        logger.warning(
            "Milestone 3 multi-model retraining "
            "cycle completed: %s",
            result,
        )

        return result

    # ======================================================
    # Stop
    # ======================================================

    def stop(self):
        """
        Stop the R5 retraining scheduler.
        """

        if (
            self.retraining_scheduler
            is not None
        ):

            self.retraining_scheduler.stop()

            logger.info(
                "R5 retraining scheduler stopped"
            )

    # ======================================================
    # Health
    # ======================================================

    @bentoml.api
    def health(self) -> dict:

        try:

            sample = [
                [5.1, 3.5, 1.4, 0.2]
            ]

            # ------------------------------------------------
            # Production model
            # ------------------------------------------------

            prediction = self.model.predict(
                sample
            )[0]

            self.model.predict_proba(
                sample
            )

            # ------------------------------------------------
            # Canary model
            # ------------------------------------------------

            (
                canary_model,
                canary_alias,
                canary_version,
                canary_bucket,
            ) = select_model(
                sample[0],
                self.canary_models,
            )

            canary_prediction = (
                canary_model.predict(
                    sample
                )[0]
            )

            # ------------------------------------------------
            # Unified model health
            # ------------------------------------------------

            multi_model_health = (
                MULTI_MODEL_MANAGER.health()
            )

            return {

                "status": "healthy",

                "model_version": str(
                    self.model_version
                ),

                "prediction": TARGET_NAMES[
                    prediction
                ],

                "canary_prediction": (
                    TARGET_NAMES[
                        canary_prediction
                    ]
                ),

                "canary_model_version": (
                    str(canary_version)
                ),

                "canary_model_alias": (
                    canary_alias
                ),

                "canary_bucket": (
                    canary_bucket
                ),

                "multi_model": (
                    multi_model_health
                ),
            }

        except Exception as exc:

            self.error_count += 1

            logger.exception(
                "Health check failed"
            )

            return {
                "status": "unhealthy",
                "error": str(exc),
            }

    # ======================================================
    # Runtime Metrics
    # ======================================================

    @bentoml.api(route="/metrics/json")
    def metrics(self) -> dict:

        avg_prediction_latency = (
            self.total_single_latency
            / self.total_single_predictions
            if self.total_single_predictions
            else 0.0
        )

        avg_batch_latency = (
            self.total_batch_latency
            / self.total_batches
            if self.total_batches
            else 0.0
        )

        return {

            "total_predictions":
                self.total_predictions,

            "total_batches":
                self.total_batches,

            "average_prediction_latency_ms":
                round(
                    avg_prediction_latency,
                    2,
                ),

            "average_batch_latency_ms":
                round(
                    avg_batch_latency,
                    2,
                ),

            "error_count":
                self.error_count,

            "model_version":
                str(self.model_version),

            # ------------------------------------------------
            # Per-model A/B metrics
            # ------------------------------------------------

            "multi_model_metrics": {
                model_name:
                    MULTI_MODEL_MANAGER.get_ab_metrics(
                        model_name
                    )
                for model_name
                in MULTI_MODEL_MANAGER.versioned_adapters
            },

        }

    # ======================================================
    # Iris Single Prediction
    # ======================================================

    @bentoml.api
    def predict(
        self,
        request: IrisRequest,
    ) -> PredictionResponse:

        start = time.perf_counter()

        try:

            # ------------------------------------------------
            # Existing Iris Canary Selection
            # ------------------------------------------------

            (
                model,
                selected_alias,
                selected_version,
                bucket,
            ) = select_model(
                request.features,
                self.canary_models,
            )

            logger.info(
                "Canary routing: "
                "alias=%s version=%s bucket=%s",
                selected_alias,
                selected_version,
                bucket,
            )

            # ------------------------------------------------
            # Prediction
            # ------------------------------------------------

            prediction = model.predict(
                [request.features]
            )[0]

            probabilities = (
                model.predict_proba(
                    [request.features]
                )[0]
            )

            confidence = float(
                np.max(probabilities)
            )

            # ------------------------------------------------
            # Latency
            # ------------------------------------------------

            latency = (
                time.perf_counter()
                - start
            ) * 1000

            # ------------------------------------------------
            # Monitoring
            # ------------------------------------------------

            request_id = str(
                uuid.uuid4()
            )

            log_prediction(
                request_id=request_id,
                model_version=str(
                    selected_version
                ),
                latency_ms=latency,
                prediction=TARGET_NAMES[
                    prediction
                ],
                input_features=(
                    request.features
                ),
            )

            # ------------------------------------------------
            # Runtime Metrics
            # ------------------------------------------------

            self.total_predictions += 1

            self.total_single_predictions += 1

            self.total_single_latency += latency

            # ------------------------------------------------
            # Probability Response
            # ------------------------------------------------

            probability_dict = {
                TARGET_NAMES[i]:
                    float(probabilities[i])
                for i in range(
                    len(TARGET_NAMES)
                )
            }

            return PredictionResponse(

                prediction=TARGET_NAMES[
                    prediction
                ],

                confidence=confidence,

                model_version=str(
                    selected_version
                ),

                latency_ms=round(
                    latency,
                    2,
                ),

                probabilities=(
                    probability_dict
                ),
            )

        except Exception:

            self.error_count += 1

            logger.exception(
                "Prediction failed"
            )

            raise

    # ======================================================
    # Iris Batch Prediction
    # ======================================================

    @bentoml.api
    def predict_batch(
        self,
        request: IrisBatchRequest,
    ) -> dict:

        batch_start = (
            time.perf_counter()
        )

        try:

            results = []

            for features in request.features:

                # --------------------------------------------
                # Canary Model Selection
                # --------------------------------------------

                (
                    model,
                    selected_alias,
                    selected_version,
                    bucket,
                ) = select_model(
                    features,
                    self.canary_models,
                )

                logger.info(
                    "Batch canary routing: "
                    "alias=%s version=%s bucket=%s",
                    selected_alias,
                    selected_version,
                    bucket,
                )

                # --------------------------------------------
                # Prediction timing
                # --------------------------------------------

                prediction_start = (
                    time.perf_counter()
                )

                prediction = model.predict(
                    [features]
                )[0]

                probabilities = (
                    model.predict_proba(
                        [features]
                    )[0]
                )

                prediction_latency = (
                    time.perf_counter()
                    - prediction_start
                ) * 1000

                # --------------------------------------------
                # Monitoring
                # --------------------------------------------

                request_id = str(
                    uuid.uuid4()
                )

                log_prediction(
                    request_id=request_id,
                    model_version=str(
                        selected_version
                    ),
                    latency_ms=(
                        prediction_latency
                    ),
                    prediction=TARGET_NAMES[
                        prediction
                    ],
                    input_features=features,
                )

                # --------------------------------------------
                # Response
                # --------------------------------------------

                probability_dict = {
                    TARGET_NAMES[i]:
                        float(probabilities[i])
                    for i in range(
                        len(TARGET_NAMES)
                    )
                }

                results.append({

                    "prediction":
                        TARGET_NAMES[
                            prediction
                        ],

                    "confidence":
                        float(
                            np.max(
                                probabilities
                            )
                        ),

                    "probabilities":
                        probability_dict,

                    "latency_ms":
                        round(
                            prediction_latency,
                            2,
                        ),

                    "model_version":
                        str(
                            selected_version
                        ),

                    "model_alias":
                        selected_alias,
                })

            # --------------------------------------------
            # Batch latency
            # --------------------------------------------

            batch_latency = (
                time.perf_counter()
                - batch_start
            ) * 1000

            # --------------------------------------------
            # Runtime metrics
            # --------------------------------------------

            self.total_predictions += (
                len(request.features)
            )

            self.total_batches += 1

            self.total_batch_latency += (
                batch_latency
            )

            return {

                "predictions":
                    results,

                "batch_size":
                    len(request.features),

                "batch_latency_ms":
                    round(
                        batch_latency,
                        2,
                    ),
            }

        except Exception:

            self.error_count += 1

            logger.exception(
                "Batch prediction failed"
            )

            raise

    # ======================================================
    # R5 Per-Model Monitoring Summary
    # ======================================================

    @bentoml.api(route="/metrics/summary")
    def metrics_summary(self) -> dict:
        """
        Return aggregate and per-model metrics.
        """

        return get_summary()

    # ======================================================
    # R4/R5 Retraining Check
    # ======================================================

    @bentoml.api(route="/retrain/check")
    def retrain_check(
        self,
        request: RetrainingCheckRequest,
    ) -> dict:

        try:

            result = check_retraining_needed(
                request.recent_inputs
            )

            logger.info(
                "Retraining check: %s",
                result,
            )

            return result

        except Exception:

            logger.exception(
                "Retraining check failed"
            )

            raise

    # ======================================================
    # R5 Scheduled Retraining Check
    # ======================================================

    def _scheduled_retraining_check(
        self,
    ):
        """
        Scheduled R5 workflow:

        monitoring.db
             ↓
        recent inputs
             ↓
        drift calculation
             ↓
        threshold exceeded?
             ↓
            YES
             ↓
        retraining
             ↓
        evaluation
             ↓
        promotion gate
             ↓
        staging
             ↓
        production
        """

        logger.info(
            "R5 scheduled retraining check started"
        )

        recent_inputs = get_recent_inputs(
            limit=MONITORING_INPUT_LIMIT
        )

        logger.info(
            "R5 scheduler found %s recent inputs",
            len(recent_inputs),
        )

        # --------------------------------------------------
        # Enough data?
        # --------------------------------------------------

        if (
            len(recent_inputs)
            < MIN_RETRAINING_SAMPLES
        ):

            result = {

                "status": "skipped",

                "reason":
                    "not_enough_recent_inputs",

                "sample_count":
                    len(recent_inputs),
            }

            logger.info(
                "R5 scheduled check skipped: %s",
                result,
            )

            return result

        # --------------------------------------------------
        # Automated Retraining
        # --------------------------------------------------

        result = automated_retrain(
            recent_inputs=recent_inputs,
            retrain_callback=(
                self._run_retraining_pipeline
            ),
        )

        logger.warning(
            "R5 scheduled retraining result: %s",
            result,
        )

        return result

    # ======================================================
    # R5 Actual Retraining Pipeline
    # ======================================================

    def _run_retraining_pipeline(self):
        """
        Execute the actual Iris retraining workflow.

        train
          ↓
        evaluate candidate
          ↓
        promotion threshold
          ↓
        compare with production
          ↓
        staging
          ↓
        production
          ↓
        reload service model
        """

        logger.warning(
            "=========================================="
        )

        logger.warning(
            "R5 AUTOMATED RETRAINING STARTED"
        )

        logger.warning(
            "=========================================="
        )

        # --------------------------------------------------
        # Train candidate model
        # --------------------------------------------------

        from src.train import train

        candidate_model = train()

        logger.info(
            "Training completed: %s",
            type(candidate_model).__name__,
        )

        # --------------------------------------------------
        # Evaluation dataset
        # --------------------------------------------------

        iris = load_iris()

        _, X_test, _, y_test = (
            train_test_split(
                iris.data,
                iris.target,
                test_size=TEST_SIZE,
                random_state=RANDOM_STATE,
                stratify=iris.target,
            )
        )

        # --------------------------------------------------
        # Candidate evaluation
        # --------------------------------------------------

        candidate_accuracy = float(
            candidate_model.score(
                X_test,
                y_test,
            )
        )

        logger.warning(
            "Candidate model accuracy: %.4f",
            candidate_accuracy,
        )

        # --------------------------------------------------
        # Promotion threshold
        # --------------------------------------------------

        if not should_promote(
            candidate_accuracy
        ):

            logger.warning(
                "Candidate model rejected: "
                "accuracy %.4f is below "
                "promotion threshold %.4f",
                candidate_accuracy,
                PROMOTION_ACCURACY_THRESHOLD,
            )

            return {

                "status": "rejected",

                "reason":
                    "promotion_threshold_not_met",

                "candidate_accuracy":
                    candidate_accuracy,

                "promotion_threshold":
                    PROMOTION_ACCURACY_THRESHOLD,
            }

        # --------------------------------------------------
        # Current production evaluation
        # --------------------------------------------------

        production_accuracy = float(
            self.model.score(
                X_test,
                y_test,
            )
        )

        logger.warning(
            "Current production model accuracy: %.4f",
            production_accuracy,
        )

        # --------------------------------------------------
        # Candidate must not be worse
        # --------------------------------------------------

        if (
            candidate_accuracy
            < production_accuracy
        ):

            logger.warning(
                "Candidate model rejected: "
                "candidate accuracy %.4f is lower "
                "than production accuracy %.4f",
                candidate_accuracy,
                production_accuracy,
            )

            return {

                "status": "rejected",

                "reason":
                    "candidate_worse_than_production",

                "candidate_accuracy":
                    candidate_accuracy,

                "production_accuracy":
                    production_accuracy,
            }

        # --------------------------------------------------
        # Assign staging
        # --------------------------------------------------

        staging_version = assign_staging(
            MODEL_NAME
        )

        logger.info(
            "New model assigned to staging: %s",
            staging_version,
        )

        # --------------------------------------------------
        # Promote staging → production
        # --------------------------------------------------

        production_version = promote_model(
            MODEL_NAME,
            from_alias="staging",
            to_alias="production",
        )

        logger.warning(
            "New model promoted to production: %s",
            production_version,
        )

        # --------------------------------------------------
        # Reload production model
        # --------------------------------------------------

        self.model, self.model_version = (
            load_model()
        )

        # --------------------------------------------------
        # Reload canary models
        # --------------------------------------------------

        self.canary_models = (
            load_canary_models()
        )

        logger.warning(
            "Production model reloaded: %s",
            self.model_version,
        )

        logger.warning(
            "=========================================="
        )

        logger.warning(
            "R5 AUTOMATED RETRAINING COMPLETED"
        )

        logger.warning(
            "=========================================="
        )

        return {

            "status": "promoted",

            "production_version":
                str(
                    production_version
                ),

            "candidate_accuracy":
                candidate_accuracy,

            "production_accuracy":
                production_accuracy,
        }

    # ======================================================
    # Milestone 3 Multi-Model Retraining Endpoint
    # ======================================================

    @bentoml.api(
        route="/retrain/multimodel"
    )
    def multimodel_retraining(self) -> dict:
        """
        Run one Milestone 3 multi-model retraining
        orchestration cycle.

        The orchestrator independently checks:

        forecast
        ETA
        anomaly
        supplier risk
        """

        logger.warning(
            "Milestone 3 multi-model retraining "
            "endpoint called"
        )

        try:

            result = (
                self._run_multimodel_retraining()
            )

            return result

        except Exception as exc:

            logger.exception(
                "Milestone 3 multi-model retraining "
                "failed"
            )

            return {
                "status": "failed",
                "reason": str(exc),
            }

    # ======================================================
    # Milestone 3 Single-Model Retraining Endpoint
    # ======================================================

    @bentoml.api(
        route="/retrain/multimodel/{model_name}"
    )
    def multimodel_retraining_one(
        self,
        model_name: str,
    ) -> dict:
        """
        Run Milestone 3 orchestration for one
        specific served model.
        """

        model_name = (
            model_name.strip().lower()
        )

        valid_models = {
            "forecast",
            "eta",
            "anomaly",
            "risk",
        }

        if model_name not in valid_models:

            return {
                "status": "error",
                "reason": (
                    f"Unknown model: {model_name}"
                ),
            }

        logger.warning(
            "Milestone 3 retraining requested "
            "for model=%s",
            model_name,
        )

        try:

            result = (
                self.multimodel_orchestrator
                .run_model(model_name)
            )

            logger.warning(
                "Milestone 3 model result: %s",
                result,
            )

            return result

        except Exception as exc:

            logger.exception(
                "Multi-model retraining failed "
                "for model=%s",
                model_name,
            )

            return {
                "model_name": model_name,
                "status": "error",
                "reason": str(exc),
            }

    # ======================================================
    # R5 Manual Retraining Trigger
    # ======================================================

    @bentoml.api(
        route="/retrain/trigger"
    )
    def retrain_trigger(self) -> dict:
        """
        Manually trigger the actual R5
        Iris retraining pipeline.
        """

        logger.warning(
            "Manual retraining triggered"
        )

        try:

            result = (
                self._run_retraining_pipeline()
            )

            if isinstance(
                result,
                dict,
            ):

                if (
                    result.get("status")
                    == "rejected"
                ):

                    return {

                        "status":
                            "retraining_rejected",

                        "message":
                            "Candidate model "
                            "failed promotion gate",

                        **result,
                    }

                return {

                    "status":
                        "retraining_completed",

                    "message":
                        "Model retraining and "
                        "promotion completed",

                    **result,
                }

            return {

                "status":
                    "retraining_completed",

                "message":
                    "Model retraining and "
                    "promotion completed",

                "new_model_version":
                    str(result),
            }

        except Exception as exc:

            logger.exception(
                "Manual retraining failed"
            )

            return {

                "status":
                    "retraining_failed",

                "message":
                    str(exc),
            }

    # ======================================================
    # R5 Rollback
    # ======================================================

    @bentoml.api(
        route="/rollback"
    )
    def rollback(
        self,
        request: RollbackRequest,
    ) -> dict:
        """
        Roll back Production when the newly
        promoted model performs worse.
        """

        new_model_accuracy = (
            request.new_model_accuracy
        )

        previous_model_accuracy = (
            request.previous_model_accuracy
        )

        logger.warning(
            "R5 rollback evaluation: "
            "new_accuracy=%s previous_accuracy=%s",
            new_model_accuracy,
            previous_model_accuracy,
        )

        # --------------------------------------------------
        # Determine whether rollback is required
        # --------------------------------------------------

        rollback_required = should_rollback(
            new_model_accuracy=(
                new_model_accuracy
            ),
            previous_model_accuracy=(
                previous_model_accuracy
            ),
        )

        # --------------------------------------------------
        # No rollback
        # --------------------------------------------------

        if not rollback_required:

            logger.info(
                "Rollback not required"
            )

            return {

                "status":
                    "no_rollback",

                "message":
                    "New model performance "
                    "is acceptable",

                "new_model_accuracy":
                    new_model_accuracy,

                "previous_model_accuracy":
                    previous_model_accuracy,

                "current_production_version":
                    str(
                        self.model_version
                    ),
            }

        # --------------------------------------------------
        # Rollback required
        # --------------------------------------------------

        logger.warning(
            "R5 ROLLBACK TRIGGERED"
        )

        result = rollback_model(
            MODEL_NAME
        )

        # --------------------------------------------------
        # Reload production model
        # --------------------------------------------------

        self.model, self.model_version = (
            load_model()
        )

        # --------------------------------------------------
        # Reload canary models
        # --------------------------------------------------

        self.canary_models = (
            load_canary_models()
        )

        # --------------------------------------------------
        # Add evaluation information
        # --------------------------------------------------

        result["new_model_accuracy"] = (
            new_model_accuracy
        )

        result["previous_model_accuracy"] = (
            previous_model_accuracy
        )

        result[
            "current_production_version"
        ] = str(
            self.model_version
        )

        logger.warning(
            "R5 rollback completed. "
            "Production version=%s",
            self.model_version,
        )

        return result