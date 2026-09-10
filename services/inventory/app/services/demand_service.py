from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.sales_history import SalesHistory


def calculate_rolling_average_demand(
    db: Session,
    sku_id: str,
    warehouse_id: str,
    days: int = 30,
) -> float:

    if days <= 0:
        raise ValueError(
            "Demand window must be greater than zero"
        )

    end_date = date.today()

    start_date = (
        end_date
        - timedelta(days=days - 1)
    )

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

        if record.quantity_sold < 0:
            raise ValueError(
                "Negative demand data is not allowed"
            )

        total_quantity += record.quantity_sold

    if not records:
        return 0.0

    # Use the actual number of observed days
    # instead of always dividing by 30.
    first_sale_date = min(
        record.sale_date
        for record in records
    )

    observed_days = (
        end_date - first_sale_date
    ).days + 1

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
        raise ValueError(
            "Demand window must be greater than zero"
        )

    start_date = (
        date.today()
        - timedelta(days=days - 1)
    )

    end_date = date.today()

    records = (
        db.query(SalesHistory)
        .filter(
            SalesHistory.sale_date >= start_date,
            SalesHistory.sale_date <= end_date,
        )
        .all()
    )

    totals = defaultdict(int)
    first_sale_dates = {}

    for record in records:

        if record.quantity_sold < 0:
            raise ValueError(
                "Negative demand data is not allowed"
            )

        key = (
            record.sku_id,
            record.warehouse_id,
        )

        totals[key] += record.quantity_sold

        if (
            key not in first_sale_dates
            or record.sale_date
            < first_sale_dates[key]
        ):
            first_sale_dates[key] = (
                record.sale_date
            )

    result = {}

    for key, quantity in totals.items():

        observed_days = (
            end_date
            - first_sale_dates[key]
        ).days + 1

        effective_days = min(
            days,
            observed_days,
        )

        result[key] = round(
            quantity / effective_days,
            2,
        )

    return result