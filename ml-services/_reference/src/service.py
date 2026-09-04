
"""
BentoML service for Iris classification.

R5 Features:
- /predict
- /predict_batch
- /health
- /metrics/json
- /metrics/summary
- /retrain/check
- /retrain/trigger
- /rollback

R5:
1. Per-model monitoring
2. Automated scheduled retraining
3. Model rollback
4. Retraining and rollback integration
5. Retraining promotion evaluation gate
"""

import logging
import os
import time
import uuid

import bentoml
import numpy as np

from pydantic import BaseModel, Field, field_validator
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split

from src.monitoring import (
    get_summary,
    log_prediction,
    get_recent_inputs,
)

from src.predict import load_model

from src.canary import (
    load_canary_models,
    select_model,
)

from src.retraining import (
    check_retraining_needed,
    automated_retrain,
)

from src.scheduler import RetrainingScheduler

from src.rollback import should_rollback

from src.mlflow_utils import (
    assign_staging,
    promote_model,
    rollback_model,
)

from src.config import (
    MODEL_NAME,
    RETRAINING_INTERVAL_SECONDS,
    MIN_RETRAINING_SAMPLES,
    MONITORING_INPUT_LIMIT,
    ENABLE_RETRAINING_SCHEDULER,
    TEST_SIZE,
    RANDOM_STATE,
    PROMOTION_ACCURACY_THRESHOLD,
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
# Request Models
# ==========================================================

class IrisRequest(BaseModel):
    """
    Single prediction request.
    """

    features: list[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Exactly four Iris features",
    )


class IrisBatchRequest(BaseModel):
    """
    Batch prediction request.
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
    Request used to simulate production
    performance of the newly promoted model.
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
# Response Model
# ==========================================================

class PredictionResponse(BaseModel):
    """
    Prediction response.
    """

    prediction: str
    confidence: float
    model_version: str
    latency_ms: float
    probabilities: dict[str, float]


# ==========================================================
# BentoML Service
# ==========================================================

@bentoml.service(name="iris_service")
class IrisService:

    # ======================================================
    # Initialization
    # ======================================================

    def __init__(self):

        # --------------------------------------------------
        # Load Production Model
        # --------------------------------------------------

        self.model, self.model_version = load_model()

        # --------------------------------------------------
        # Load Canary Models
        # --------------------------------------------------

        self.canary_models = load_canary_models()

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
        # R5 Retraining Scheduler
        # --------------------------------------------------

        self.retraining_scheduler = None

        scheduler_env = os.getenv("ENABLE_RETRAINING_SCHEDULER")

        if scheduler_env is None:
            scheduler_enabled = ENABLE_RETRAINING_SCHEDULER
        else:
            scheduler_enabled = scheduler_env.strip().lower() == "true"
                    

              
        

        if scheduler_enabled:

            self.retraining_scheduler = RetrainingScheduler(
                check_function=self._scheduled_retraining_check,
                interval_seconds=RETRAINING_INTERVAL_SECONDS,
            )

            self.retraining_scheduler.start()

            logger.info(
                "R5 retraining scheduler started "
                "(interval=%s seconds)",
                RETRAINING_INTERVAL_SECONDS,
            )

        else:

            logger.info(
                "R5 retraining scheduler disabled"
            )

        logger.info(
            "Loaded production model version: %s",
            self.model_version,
        )

    # ======================================================
    # Stop Method
    # ======================================================

    def stop(self):
        """
        Stop the R5 retraining scheduler if it is running.
        """

        if self.retraining_scheduler is not None:

            self.retraining_scheduler.stop()

            logger.info(
                "R5 retraining scheduler stopped"
            )

    # ======================================================
    # Health Endpoint
    # ======================================================

    @bentoml.api
    def health(self) -> dict:

        try:

            sample = [
                [5.1, 3.5, 1.4, 0.2]
            ]

            # Production model prediction
            prediction = self.model.predict(
                sample
            )[0]

            self.model.predict_proba(
                sample
            )

            # Canary model prediction
            (
                canary_model,
                canary_alias,
                canary_version,
                canary_bucket,
            ) = select_model(
                sample[0],
                self.canary_models,
            )

            canary_prediction = canary_model.predict(
                sample
            )[0]

            return {
                "status": "healthy",

                "model_version": str(
                    self.model_version
                ),

                "prediction": TARGET_NAMES[
                    prediction
                ],

                "canary_prediction": TARGET_NAMES[
                    canary_prediction
                ],

                "canary_model_version": str(
                    canary_version
                ),

                "canary_model_alias": canary_alias,

                "canary_bucket": canary_bucket,
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
    # Metrics Endpoint
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
        }

    # ======================================================
    # Single Prediction
    # ======================================================

    @bentoml.api
    def predict(
        self,
        request: IrisRequest,
    ) -> PredictionResponse:

        start = time.perf_counter()

        try:

            # ------------------------------------------------
            # Canary / A-B Model Selection
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

            probabilities = model.predict_proba(
                [request.features]
            )[0]

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
            # R5 Monitoring
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
                input_features=request.features,
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

                probabilities=probability_dict,
            )

        except Exception:

            self.error_count += 1

            logger.exception(
                "Prediction failed"
            )

            raise

    # ======================================================
    # Batch Prediction
    # ======================================================

    @bentoml.api
    def predict_batch(
        self,
        request: IrisBatchRequest,
    ) -> dict:

        batch_start = time.perf_counter()

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
                # Prediction Timing
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
                # R5 Monitoring
                # --------------------------------------------

                request_id = str(
                    uuid.uuid4()
                )

                log_prediction(
                    request_id=request_id,
                    model_version=str(
                        selected_version
                    ),
                    latency_ms=prediction_latency,
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

                results.append(
                    {
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
                    }
                )

            # --------------------------------------------
            # Batch Latency
            # --------------------------------------------

            batch_latency = (
                time.perf_counter()
                - batch_start
            ) * 1000

            # --------------------------------------------
            # Metrics
            # --------------------------------------------

            self.total_predictions += len(
                request.features
            )

            self.total_batches += 1

            self.total_batch_latency += (
                batch_latency
            )

            return {
                "predictions": results,

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

        Includes:
        - total request volume
        - aggregate p50
        - aggregate p95
        - per-model request volume
        - per-model p50
        - per-model p95
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

    def _scheduled_retraining_check(self):
        """
        Called automatically by the R5 scheduler.

        Flow:

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
           train()
              ↓
        evaluate candidate
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

        # --------------------------------------------
        # Need enough data
        # --------------------------------------------

        if len(recent_inputs) < MIN_RETRAINING_SAMPLES:

            result = {
                "status": "skipped",
                "reason": (
                    "not_enough_recent_inputs"
                ),
                "sample_count": len(
                    recent_inputs
                ),
            }

            logger.info(
                "R5 scheduled check skipped: %s",
                result,
            )

            return result

        # --------------------------------------------
        # Automated Retraining
        # --------------------------------------------

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
        Execute the actual retraining workflow.

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

        # --------------------------------------------
        # Train candidate model
        # --------------------------------------------

        from src.train import train

        candidate_model = train()

        logger.info(
            "Training completed: %s",
            type(candidate_model).__name__,
        )

        # --------------------------------------------
        # Prepare evaluation dataset
        # --------------------------------------------

        iris = load_iris()

        _, X_test, _, y_test = train_test_split(
            iris.data,
            iris.target,
            test_size=TEST_SIZE,
            random_state=RANDOM_STATE,
            stratify=iris.target,
        )

        # --------------------------------------------
        # Evaluate candidate model
        # --------------------------------------------

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

        # --------------------------------------------
        # Promotion threshold gate
        # --------------------------------------------

        if not should_promote(candidate_accuracy):

            logger.warning(
                "Candidate model rejected: "
                "accuracy %.4f is below promotion "
                "threshold %.4f",
                candidate_accuracy,
                PROMOTION_ACCURACY_THRESHOLD,
            )

            return {
                "status": "rejected",
                "reason": "promotion_threshold_not_met",
                "candidate_accuracy": candidate_accuracy,
                "promotion_threshold":
                    PROMOTION_ACCURACY_THRESHOLD,
            }

        # --------------------------------------------
        # Evaluate current production model
        # --------------------------------------------

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

        # --------------------------------------------
        # Candidate must not be worse
        # than current production
        # --------------------------------------------

        if candidate_accuracy < production_accuracy:

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

        # --------------------------------------------
        # Assign latest model to staging
        # --------------------------------------------

        staging_version = assign_staging(
            MODEL_NAME
        )

        logger.info(
            "New model assigned to staging: %s",
            staging_version,
        )

        # --------------------------------------------
        # Promote staging → production
        # --------------------------------------------

        production_version = promote_model(
            MODEL_NAME,
            from_alias="staging",
            to_alias="production",
        )

        logger.warning(
            "New model promoted to production: %s",
            production_version,
        )

        # --------------------------------------------
        # Reload production model
        # --------------------------------------------

        self.model, self.model_version = (
            load_model()
        )

        # --------------------------------------------
        # Reload canary models
        # --------------------------------------------

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
                str(production_version),
            "candidate_accuracy":
                candidate_accuracy,
            "production_accuracy":
                production_accuracy,
        }

    # ======================================================
    # R4/R5 Manual Retraining Trigger
    # ======================================================

    @bentoml.api(route="/retrain/trigger")
    def retrain_trigger(self) -> dict:
        """
        Manually trigger the actual R5 retraining pipeline.
        """

        logger.warning(
            "Manual retraining triggered"
        )

        try:

            result = (
                self._run_retraining_pipeline()
            )

            if isinstance(result, dict):

                if result.get("status") == "rejected":

                    return {
                        "status":
                            "retraining_rejected",

                        "message":
                            "Candidate model failed promotion gate",

                        **result,
                    }

                return {
                    "status":
                        "retraining_completed",

                    "message":
                        "Model retraining and promotion completed",

                    **result,
                }

            return {
                "status":
                    "retraining_completed",

                "message":
                    "Model retraining and promotion completed",

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

    @bentoml.api(route="/rollback")
    def rollback(
        self,
        new_model_accuracy: float,
        previous_model_accuracy: float,
    ) -> dict:
        """
        Roll back Production when the newly promoted
        model performs worse.

        Example:

        New model       = 0.70
        Previous model  = 0.92

        Result:
            Production -> previous version
        """

        logger.warning(
            "R5 rollback evaluation: "
            "new_accuracy=%s previous_accuracy=%s",
            new_model_accuracy,
            previous_model_accuracy,
        )

        # --------------------------------------------------
        # Validate accuracy values
        # --------------------------------------------------

        if not 0.0 <= new_model_accuracy <= 1.0:
            raise ValueError(
                "new_model_accuracy must be between 0.0 and 1.0"
            )

        if not 0.0 <= previous_model_accuracy <= 1.0:
            raise ValueError(
                "previous_model_accuracy must be between 0.0 and 1.0"
            )

        # --------------------------------------------------
        # Decide whether rollback is required
        # --------------------------------------------------

        rollback_required = should_rollback(
            new_model_accuracy=new_model_accuracy,
            previous_model_accuracy=previous_model_accuracy,
        )

        # --------------------------------------------------
        # New model is acceptable
        # --------------------------------------------------

        if not rollback_required:

            logger.info(
                "Rollback not required"
            )

            return {
                "status": "no_rollback",
                "message": (
                    "New model performance is acceptable"
                ),
                "new_model_accuracy": new_model_accuracy,
                "previous_model_accuracy": (
                    previous_model_accuracy
                ),
                "current_production_version": str(
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

        result["current_production_version"] = (
            str(self.model_version)
        )

        logger.warning(
            "R5 rollback completed. "
            "Production version=%s",
            self.model_version,
        )

        return result

