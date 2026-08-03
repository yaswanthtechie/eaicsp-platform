"""
BentoML service for Demand Forecasting.

Features:
- Forecast prediction
- Health endpoint
- Metrics endpoint
- Latency measurement
"""

import time

import bentoml
from pydantic import BaseModel, Field

from predict import predict


class ForecastRequest(BaseModel):
    """Forecast request."""

    sku_id: str = Field(...)

    warehouse_id: str = Field(...)

    horizon_days: int = Field(
        default=30,
        gt=0
    )


class ForecastResponse(BaseModel):
    """Forecast response."""

    forecast: list

    model_version: str

    latency_ms: float


@bentoml.service(name="forecast_service")
class ForecastService:

    def __init__(self):

        self.model_version = "1.0"

        self.total_predictions = 0

        self.total_latency = 0.0

        self.error_count = 0

    @bentoml.api
    def health(self) -> dict:
        """
        Health check.
        """

        try:

            result = predict(1)

            return {

                "status": "healthy",

                "model_version": self.model_version,

                "sample_forecast":
                    result["forecast"][0]

            }

        except Exception as e:

            return {

                "status": "unhealthy",

                "error": str(e)

            }

    @bentoml.api
    def service_metrics(self) -> dict:
        """
        Service metrics.
        """

        avg_latency = 0

        if self.total_predictions > 0:

            avg_latency = (

                self.total_latency

                / self.total_predictions

            )

        return {

            "model_version":
                self.model_version,

            "total_predictions":
                self.total_predictions,

            "average_latency_ms":
                round(avg_latency, 3),

            "error_count":
                self.error_count

        }

    @bentoml.api
    def predict(
        self,
        request: ForecastRequest
    ) -> ForecastResponse:

        start = time.perf_counter()

        try:

            # Currently sku_id and warehouse_id
            # are accepted to satisfy API contract.
            # The Prophet model is global.

            result = predict(
                request.horizon_days
            )

            latency = (

                time.perf_counter()

                - start

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