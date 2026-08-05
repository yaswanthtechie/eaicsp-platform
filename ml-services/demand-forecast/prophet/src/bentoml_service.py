"""
BentoML service for Demand Forecasting.

Features
--------
- Health endpoint
- Prediction endpoint
- Service metrics
- Best Ensemble (Prophet + XGBoost)
"""

import time
print("Loaded:", __file__)

import bentoml
from pydantic import BaseModel, Field

from src.predict import predict


# =====================================================
# Request
# =====================================================

class ForecastRequest(BaseModel):
    """Prediction request."""

    sku_id: str = Field(...)

    warehouse_id: str = Field(...)

    horizon_months: int = Field(
        default=6,
        gt=0,
        description="Number of future months to forecast."
    )


# =====================================================
# Response
# =====================================================

class ForecastResponse(BaseModel):
    """Prediction response."""

    forecast: list

    model_version: str

    latency_ms: float


# =====================================================
# Service
# =====================================================

@bentoml.service(name="forecast_service")
class ForecastService:

    def __init__(self):

        self.model_version = "1.0"

        self.total_predictions = 0

        self.total_latency = 0.0

        self.error_count = 0


    # =================================================
    # Health
    # =================================================

    @bentoml.api
    def health(self) -> dict:

        try:

            result = predict(1)

            return {

                "status": "healthy",

                "model_version": self.model_version,

                "sample_forecast": result["forecast"][0]

            }

        except Exception as e:

            return {

                "status": "unhealthy",

                "error": str(e)

            }


    # =================================================
    # Metrics
    # =================================================

    @bentoml.api
    def service_metrics(self) -> dict:

        avg_latency = 0

        if self.total_predictions > 0:

            avg_latency = (
                self.total_latency
                / self.total_predictions
            )

        return {

            "model_version": self.model_version,

            "total_predictions": self.total_predictions,

            "average_latency_ms": round(avg_latency, 3),

            "error_count": self.error_count

        }


    # =================================================
    # Prediction
    # =================================================

    @bentoml.api
    def predict(
        self,
        request: ForecastRequest
    ) -> ForecastResponse:

        start = time.perf_counter()

        try:

            result = predict(
                request.horizon_months
            )

            latency = (
                time.perf_counter() - start
            ) * 1000

            self.total_predictions += 1

            self.total_latency += latency

            return ForecastResponse(

                forecast=result["forecast"],

                model_version=self.model_version,

                latency_ms=round(latency, 3)

            )

        except Exception as e:

            self.error_count += 1

            raise e