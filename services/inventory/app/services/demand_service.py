from collections import defaultdict
from datetime import date, timedelta
from typing import cast

from sqlalchemy.orm import Session

from app.models.sales_history import SalesHistory


def calculate_rolling_average_demand(
    db: Session,
    sku_id: str,
    warehouse_id: str,
    days: int = 30,
    end_date: date | None = None,
) -> float:
    """Average daily demand over the `days` ending at end_date (default: today)."""
    if days <= 0:
        raise ValueError("Demand window must be greater than zero")
    end_date = end_date or date.today()

    start_date = end_date - timedelta(days=days - 1)

    records = (
        db.query(SalesHistory)
        .filter(
            SalesHistory.sku_id == sku_id,
            SalesHistory.warehouse_id == warehouse_id,
            SalesHistory.sale_date >= start_date,
            SalesHistory.sale_date <= end_date,
        )
        .all()
    )

    total_quantity = 0

    for record in records:
        qty = int(record.quantity_sold)
        if qty < 0:
            raise ValueError("Negative demand data is not allowed")

        total_quantity += qty

    if not records:
        return 0.0

    # Use the actual number of observed days
    # instead of always dividing by 30.
    first_sale_date: date = min(cast(date, record.sale_date) for record in records)

    observed_days = (end_date - first_sale_date).days + 1

    effective_days = min(
        days,
        observed_days,
    )

    return round(
        total_quantity / effective_days,
        2,
    )


def calculate_rolling_average_demand_all(
    db: Session,
    days: int = 30,
):
    if days <= 0:
        raise ValueError("Demand window must be greater than zero")

    start_date = date.today() - timedelta(days=days - 1)

    end_date = date.today()

    records = (
        db.query(SalesHistory)
        .filter(
            SalesHistory.sale_date >= start_date,
            SalesHistory.sale_date <= end_date,
        )
        .all()
    )

    totals: dict[tuple[str, str], int] = defaultdict(int)
    first_sale_dates: dict[tuple[str, str], date] = {}

    for record in records:
        qty = int(record.quantity_sold)
        if qty < 0:
            raise ValueError("Negative demand data is not allowed")

        key = (
            str(record.sku_id),
            str(record.warehouse_id),
        )

        totals[key] += qty

        r_date = cast(date, record.sale_date)
        if key not in first_sale_dates or r_date < first_sale_dates[key]:
            first_sale_dates[key] = r_date

    result = {}

    for key, quantity in totals.items():
        observed_days = (end_date - first_sale_dates[key]).days + 1

        effective_days = min(
            days,
            observed_days,
        )

        result[key] = round(
            quantity / effective_days,
            2,
        )

    return result
