"""
BentoML service for Iris classification.

Provides:
- /predict
- /predict_batch
- /health
- /metrics
"""

import logging
import time

import bentoml
import numpy as np
from pydantic import BaseModel, Field, field_validator
from sklearn.datasets import load_iris

from src.predict import load_model


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TARGET_NAMES = load_iris().target_names


# ==========================================================
# Request Models
# ==========================================================

class IrisRequest(BaseModel):
    """Single prediction request."""

    features: list[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Exactly four Iris features",
    )


class IrisBatchRequest(BaseModel):
    """Batch prediction request."""

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
# Response Model
# ==========================================================

class PredictionResponse(BaseModel):
    """Prediction response."""

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


    def __init__(self):

        self.model, self.model_version = load_model()


        # ==============================================
        # Prediction Metrics
        # ==============================================

        # Total predictions (single + batch)
        self.total_predictions = 0


        # Single prediction metrics
        self.total_single_predictions = 0
        self.total_single_latency = 0.0


        # Batch prediction metrics
        self.total_batches = 0
        self.total_batch_latency = 0.0


        # Errors
        self.error_count = 0


        logger.info(
            "Loaded model version: %s",
            self.model_version,
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


            prediction = self.model.predict(
                sample
            )[0]


            self.model.predict_proba(
                sample
            )


            return {

                "status": "healthy",

                "model_version":
                    str(self.model_version),

                "canary_prediction":
                    TARGET_NAMES[prediction],

            }


        except Exception as e:


            self.error_count += 1


            logger.exception(
                "Health check failed"
            )


            return {

                "status": "unhealthy",

                "error": str(e),

            }



    # ======================================================
    # Metrics Endpoint
    # ======================================================

    @bentoml.api
    def metrics(self) -> dict:


        avg_prediction_latency = (

            self.total_single_latency /
            self.total_single_predictions

            if self.total_single_predictions

            else 0.0

        )


        avg_batch_latency = (

            self.total_batch_latency /
            self.total_batches

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


            prediction = self.model.predict(

                [request.features]

            )[0]


            probabilities = self.model.predict_proba(

                [request.features]

            )[0]


            confidence = float(

                np.max(probabilities)

            )


            latency = (

                time.perf_counter()
                - start

            ) * 1000



            # ================================
            # Update Metrics
            # ================================

            self.total_predictions += 1


            self.total_single_predictions += 1


            self.total_single_latency += latency



            probability_dict = {


                TARGET_NAMES[i]:
                    float(probabilities[i])


                for i in range(
                    len(TARGET_NAMES)
                )

            }



            return PredictionResponse(


                prediction=
                    TARGET_NAMES[prediction],


                confidence=
                    confidence,


                model_version=
                    str(self.model_version),


                latency_ms=
                    round(
                        latency,
                        2,
                    ),


                probabilities=
                    probability_dict,

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


        start = time.perf_counter()


        try:


            predictions = self.model.predict(

                request.features

            )


            probabilities = self.model.predict_proba(

                request.features

            )


            latency = (

                time.perf_counter()
                - start

            ) * 1000



            # ================================
            # Update Metrics
            # ================================

            self.total_predictions += len(
                request.features
            )


            self.total_batches += 1


            self.total_batch_latency += latency



            results = []



            for pred, probs in zip(
                predictions,
                probabilities,
            ):


                results.append(

                    {


                        "prediction":
                            TARGET_NAMES[pred],


                        "confidence":
                            float(
                                np.max(probs)
                            ),


                        "probabilities":
                            {

                                TARGET_NAMES[i]:
                                    float(probs[i])


                                for i in range(
                                    len(TARGET_NAMES)
                                )

                            },


                        "latency_ms":
                            round(
                                latency,
                                2,
                            ),


                        "model_version":
                            str(
                                self.model_version
                            ),

                    }

                )



            return {


                "predictions":
                    results,


                "batch_latency_ms":
                    round(
                        latency,
                        2,
                    ),

            }



        except Exception:


            self.error_count += 1


            logger.exception(
                "Batch prediction failed"
            )


            raise