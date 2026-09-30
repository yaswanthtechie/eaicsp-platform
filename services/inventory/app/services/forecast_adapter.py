"""
How Inventory will consume a demand forecast.

Contract-first only: nothing calls this yet, and there is no
HTTP call to the Forecast Service. It pins down the rules so
wiring it in later is a small change to demand_service:

1. Only use a forecast for the same SKU and warehouse.
2. Only use a fresh forecast (FORECAST_MAX_AGE_DAYS).
3. Only use a forecast that covers the date in question.
4. Otherwise fall back to the historical rolling average.

A monthly forecast is converted to the daily figures the
reorder-point and safety-stock maths already use.
"""

from calendar import monthrange
from datetime import date, datetime, timedelta
from math import sqrt
from statistics import NormalDist

from app.core.config import settings
from app.schemas.forecast import ForecastContract


def _point_for(
    contract: ForecastContract,
    on_date: date,
):
    month_start = on_date.replace(day=1)

    for point in contract.forecast:
        if point.date == month_start:
            return point

    return None


def daily_demand_from_forecast(
    contract: ForecastContract,
    on_date: date,
):
    """
    Daily mean and daily standard deviation for on_date's
    month, or None when the forecast does not cover it.

    mean  = monthly predicted / days in month
    sigma = monthly sigma / sqrt(days in month)

    monthly sigma comes from the prediction band:
    (upper - lower) / (2 * z) where z matches interval_level
    (e.g. 1.2816 for an 80% band). Dividing by sqrt(days)
    assumes days within the month are independent.
    """

    point = _point_for(contract, on_date)

    if point is None:
        return None

    days_in_month = monthrange(on_date.year, on_date.month)[1]

    z = NormalDist().inv_cdf(
        0.5 + contract.interval_level / 2
    )

    monthly_sigma = (point.upper - point.lower) / (2 * z)

    return {
        "daily_demand": point.predicted / days_in_month,
        "daily_std": monthly_sigma / sqrt(days_in_month),
    }


def resolve_daily_demand(
    contract: ForecastContract | None,
    sku_id: str,
    warehouse_id: str,
    on_date: date,
    now: datetime,
    history_daily_demand: float,
):
    """
    Pick the demand figure Inventory should plan with.

    Returns the forecast-based figure when the forecast is
    usable, otherwise the historical average, and says which
    one was used and why.
    """

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
