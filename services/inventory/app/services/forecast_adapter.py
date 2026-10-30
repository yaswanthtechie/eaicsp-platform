"""
Daily demand forecast adapter for Inventory.

Uses a forecast only when:
1. SKU and warehouse match.
2. Forecast is fresh.
3. Forecast covers the requested date.

Otherwise, Inventory uses historical demand as its fallback.
"""

from datetime import date, datetime, timedelta
from statistics import NormalDist

from app.core.config import settings
from app.schemas.forecast import ForecastContract


def _point_for(
    contract: ForecastContract,
    on_date: date,
):
    for point in contract.forecast:
        if point.date == on_date:
            return point

    return None


def daily_demand_from_forecast(
    contract: ForecastContract,
    on_date: date,
):
    """
    Return daily mean and standard deviation for the requested date.

    For a central prediction interval:
        sigma = (upper_bound - lower_bound) / (2 * z)

    The interval level determines z.
    """

    point = _point_for(contract, on_date)

    if point is None:
        return None

    z = NormalDist().inv_cdf(
        0.5 + contract.interval_level / 2
    )

    daily_std = (
        point.upper_bound - point.lower_bound
    ) / (2 * z)

    return {
        "daily_demand": point.predicted,
        "daily_std": daily_std,
    }


def resolve_daily_demand(
    contract: ForecastContract | None,
    sku_id: str,
    warehouse_id: str,
    on_date: date,
    now: datetime,
    history_daily_demand: float,
):
    """Use a valid daily forecast or fall back to historical demand."""

    def from_history(reason):
        return {
            "daily_demand": history_daily_demand,
            "daily_std": None,
            "source": "history",
            "reason": reason,
        }

    if contract is None:
        return from_history("No forecast available")

    if (
        contract.sku_id != sku_id
        or contract.warehouse_id != warehouse_id
    ):
        return from_history(
            "Forecast is for a different SKU or warehouse"
        )

    age = now - contract.generated_at

    if age < timedelta(0):
        return from_history("Forecast generation time is in the future")

    if age > timedelta(days=settings.FORECAST_MAX_AGE_DAYS):
        return from_history(
            f"Forecast is stale ({age.days} days old)"
        )

    daily = daily_demand_from_forecast(contract, on_date)

    if daily is None:
        return from_history(
            "Forecast does not cover this date"
        )

    return {
        **daily,
        "source": "forecast",
        "reason": (
            f"Forecast {contract.model_version} "
            f"generated {contract.generated_at.date()}"
        ),
    }
