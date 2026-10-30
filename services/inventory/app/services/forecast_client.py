"""
Demand Forecast Client (Flow A, blueprint section 4)

Connects Inventory Service to the Forecast Serving API:
  GET /api/v1/demand/forecast/{sku_id}?warehouse_id={warehouse_id}&horizon=30

Resilience Rules:
1. Calls forecast serving API with service API key (X-API-Key).
2. Configurable timeout (default: 2.0s).
3. Retries once on timeout, connection error, or 5xx response.
4. If unavailable, falls back to 28-day rolling sales average with forecast_source="fallback".
5. Only uses a forecast for the same SKU and warehouse that is not older than FORECAST_MAX_AGE_DAYS
   (same rules as forecast_adapter.resolve_daily_demand).
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.forecast import ForecastServingResponse
from app.services.demand_service import calculate_rolling_average_demand

logger = logging.getLogger(__name__)


class ForecastUnavailable(Exception):
    """Forecast Service is down: timeout, connection error or 5xx after all retries."""


@dataclass
class DemandForecastResult:
    """Resolved demand figure for reorder recommendation."""

    daily_demand: float
    forecast_demand: float
    forecast_source: Literal["model", "fallback"]
    model_version: Optional[str] = None
    service_unavailable: bool = False


def _is_usable(
    forecast: ForecastServingResponse,
    sku_id: str,
    warehouse_id: str,
) -> bool:
    """Same SKU and warehouse, and not stale."""
    if forecast.sku_id != sku_id or forecast.warehouse_id != warehouse_id:
        logger.warning(
            "Forecast is for %s at %s, expected %s at %s; using fallback",
            forecast.sku_id,
            forecast.warehouse_id,
            sku_id,
            warehouse_id,
        )
        return False

    generated_at = forecast.generated_at
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - generated_at
    if age > timedelta(days=settings.FORECAST_MAX_AGE_DAYS):
        logger.warning(
            "Forecast for %s at %s is stale (%d days old); using fallback",
            sku_id,
            warehouse_id,
            age.days,
        )
        return False

    return True


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
        self.api_key = settings.FORECAST_SERVICE_API_KEY if api_key is None else api_key
        self.timeout = settings.FORECAST_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
        self.max_retries = settings.FORECAST_RETRY_COUNT if max_retries is None else max_retries

        if not self.api_key:
            logger.warning(
                "FORECAST_SERVICE_API_KEY is not set; forecast calls will be rejected "
                "and recommendations will use the fallback"
            )

    def fetch_forecast(
        self,
        sku_id: str,
        warehouse_id: str,
        horizon: int = 30,
    ) -> Optional[ForecastServingResponse]:
        """
        Call Forecast Service: GET /api/v1/demand/forecast/{sku_id}
        Returns the parsed forecast, or None on a 4xx or a response that does not match the contract.
        Raises ForecastUnavailable on timeout, connection error or 5xx after all retries.
        """
        url = f"{self.base_url}/api/v1/demand/forecast/{sku_id}"
        params = {
            "warehouse_id": warehouse_id,
            "horizon": horizon,
        }
        headers = {
            "X-Caller-Service": "inventory-service",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        total_attempts = 1 + self.max_retries

        for attempt in range(1, total_attempts + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.get(url, params=params, headers=headers)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                logger.warning(
                    "Forecast service call failed on attempt %d/%d for SKU %s (%s)",
                    attempt,
                    total_attempts,
                    sku_id,
                    type(exc).__name__,
                )
                continue

            if response.status_code in (500, 502, 503, 504):
                logger.warning(
                    "Forecast service returned %d on attempt %d/%d for SKU %s at %s",
                    response.status_code,
                    attempt,
                    total_attempts,
                    sku_id,
                    warehouse_id,
                )
                continue

            if response.status_code != 200:
                # 400, 401, 404 - client errors; do not retry
                logger.warning(
                    "Forecast service returned client error %d for SKU %s at %s: %s",
                    response.status_code,
                    sku_id,
                    warehouse_id,
                    response.text,
                )
                return None

            try:
                return ForecastServingResponse.model_validate(response.json())
            except Exception as exc:
                logger.error(
                    "Forecast for SKU %s does not match contracts/openapi/forecast.yaml: %s",
                    sku_id,
                    exc,
                )
                return None

        raise ForecastUnavailable(
            f"Forecast service unavailable after {total_attempts} attempts"
        )

    def resolve_demand(
        self,
        db: Session,
        sku_id: str,
        warehouse_id: str,
        horizon: int = 30,
        fallback_days: int = 28,
        use_remote: bool = True,
    ) -> DemandForecastResult:
        """
        Resolve demand for an inventory item:
        1. Attempt to fetch model forecast from Forecast Service (unless use_remote=False).
        2. If it is for this SKU/warehouse and fresh, use it and mark forecast_source="model".
        3. Otherwise fall back to 28-day moving average from sales history and mark forecast_source="fallback".
        """
        forecast_response = None
        service_unavailable = False

        if use_remote:
            try:
                forecast_response = self.fetch_forecast(
                    sku_id=sku_id,
                    warehouse_id=warehouse_id,
                    horizon=horizon,
                )
            except ForecastUnavailable as exc:
                logger.warning("%s; using fallback for SKU %s at %s", exc, sku_id, warehouse_id)
                service_unavailable = True

        if forecast_response is not None and _is_usable(forecast_response, sku_id, warehouse_id):
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
            service_unavailable=service_unavailable,
        )


# Global singleton instance
forecast_client = ForecastClient()
