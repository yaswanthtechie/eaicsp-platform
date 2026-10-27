"""
Demand Forecast Client (Flow A, blueprint section 4)

Connects Inventory Service to the Forecast Serving API:
  GET /api/v1/demand/forecast/{sku_id}?warehouse_id={warehouse_id}&horizon=30

Resilience Rules:
1. Calls forecast serving API with service API key (X-API-Key).
2. Configurable timeout (default: 2.0s).
3. Retries once on timeout, connection error, or 5xx response.
4. If unavailable, falls back to 28-day rolling sales average with forecast_source="fallback".
"""

import logging
from dataclasses import dataclass
from typing import Literal, Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.forecast import ForecastServingResponse
from app.services.demand_service import calculate_rolling_average_demand

logger = logging.getLogger(__name__)


@dataclass
class DemandForecastResult:
    """Resolved demand figure for reorder recommendation."""

    daily_demand: float
    forecast_demand: float
    forecast_source: Literal["model", "fallback"]
    model_version: Optional[str] = None


class ForecastClient:
    """HTTP client for Forecast Serving API with timeout, retry, and sales fallback."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
    ):
        self.base_url = (base_url or settings.FORECAST_SERVICE_URL).rstrip("/")
        self.api_key = api_key or settings.FORECAST_SERVICE_API_KEY
        self.timeout = timeout_seconds or settings.FORECAST_TIMEOUT_SECONDS
        self.max_retries = max_retries if max_retries is not None else settings.FORECAST_RETRY_COUNT

    def fetch_forecast(
        self,
        sku_id: str,
        warehouse_id: str,
        horizon: int = 30,
    ) -> Optional[ForecastServingResponse]:
        """
        Call Forecast Service: GET /api/v1/demand/forecast/{sku_id}
        Retries once on timeout or transport error before returning None.
        """
        url = f"{self.base_url}/api/v1/demand/forecast/{sku_id}"
        params = {
            "warehouse_id": warehouse_id,
            "horizon": horizon,
        }
        headers = {
            "X-API-Key": self.api_key,
            "X-Caller-Service": "inventory-service",
            "Accept": "application/json",
        }

        total_attempts = 1 + self.max_retries

        for attempt in range(1, total_attempts + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.get(url, params=params, headers=headers)

                if response.status_code == 200:
                    payload = response.json()
                    return ForecastServingResponse.model_validate(payload)

                if response.status_code in (500, 502, 503, 504):
                    logger.warning(
                        "Forecast service returned %d on attempt %d/%d for SKU %s at %s",
                        response.status_code,
                        attempt,
                        total_attempts,
                        sku_id,
                        warehouse_id,
                    )
                    if attempt < total_attempts:
                        continue
                    return None

                # 400, 401, 404 - client errors; do not retry
                logger.warning(
                    "Forecast service returned client error %d for SKU %s at %s: %s",
                    response.status_code,
                    sku_id,
                    warehouse_id,
                    response.text,
                )
                return None

            except (httpx.TimeoutException, httpx.TransportError) as exc:
                logger.warning(
                    "Forecast service call failed on attempt %d/%d for SKU %s (%s)",
                    attempt,
                    total_attempts,
                    sku_id,
                    type(exc).__name__,
                )
                if attempt < total_attempts:
                    continue
                return None
            except Exception as exc:
                logger.error(
                    "Unexpected error parsing forecast for SKU %s: %s",
                    sku_id,
                    exc,
                )
                return None

        return None

    def resolve_demand(
        self,
        db: Session,
        sku_id: str,
        warehouse_id: str,
        horizon: int = 30,
        fallback_days: int = 28,
    ) -> DemandForecastResult:
        """
        Resolve demand for an inventory item:
        1. Attempt to fetch model forecast from Forecast Service.
        2. If available, use predicted values and mark forecast_source="model".
        3. If unavailable/fails, fall back to 28-day moving average from sales history
           and mark forecast_source="fallback".
        """
        forecast_response = self.fetch_forecast(
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            horizon=horizon,
        )

        if forecast_response is not None and forecast_response.forecast:
            total_predicted = sum(p.predicted for p in forecast_response.forecast)
            num_points = len(forecast_response.forecast)
            daily_demand = round(total_predicted / max(num_points, 1), 2)
            forecast_demand = round(total_predicted, 2)

            return DemandForecastResult(
                daily_demand=daily_demand,
                forecast_demand=forecast_demand,
                forecast_source="model",
                model_version=forecast_response.model_version,
            )

        # Fallback: 28-day moving average from sales_history
        logger.info(
            "Using %d-day rolling average fallback for SKU %s at %s",
            fallback_days,
            sku_id,
            warehouse_id,
        )
        history_daily = calculate_rolling_average_demand(
            db=db,
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            days=fallback_days,
        )
        forecast_demand = round(history_daily * horizon, 2)

        return DemandForecastResult(
            daily_demand=history_daily,
            forecast_demand=forecast_demand,
            forecast_source="fallback",
            model_version=None,
        )


# Global singleton instance
forecast_client = ForecastClient()

