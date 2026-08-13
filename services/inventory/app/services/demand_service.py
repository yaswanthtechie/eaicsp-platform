from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.sales_history import SalesHistory


ROLLING_WINDOW_DAYS = 30


def calculate_rolling_average_demand(
    db: Session,
    sku_id: str,
    warehouse_id: str,
    days: int = ROLLING_WINDOW_DAYS,
) -> float:

    if days <= 0:
        raise ValueError(
            "Rolling window must be greater than zero"
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

    total_units = 0

    for record in records:

        if record.quantity_sold < 0:
            raise ValueError(
                "Negative demand data is not allowed"
            )

        total_units += record.quantity_sold

    return round(
        total_units / days,
        2,
    )