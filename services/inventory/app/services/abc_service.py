import math

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.sales_history import SalesHistory


def calculate_sales_volume(
    db: Session,
):
    records = (
        db.query(
            SalesHistory.sku_id,
            SalesHistory.warehouse_id,
            func.sum(
                SalesHistory.quantity_sold
            ).label("sales_volume"),
        )
        .group_by(
            SalesHistory.sku_id,
            SalesHistory.warehouse_id,
        )
        .all()
    )

    volumes = {}

    for record in records:

        if record.sales_volume < 0:
            raise ValueError(
                "Negative demand data is not allowed"
            )

        key = (
            record.sku_id,
            record.warehouse_id,
        )

        volumes[key] = int(
            record.sales_volume
        )

    return volumes


def classify_skus(
    db: Session,
):
    volumes = calculate_sales_volume(db)

    if not volumes:
        return {}

    sorted_items = sorted(
        volumes.items(),
        key=lambda item: (
            -item[1],
            item[0][0],
            item[0][1],
        ),
    )

    total_items = len(sorted_items)

    if total_items == 0:
        return {}

    a_cutoff = math.ceil(
        total_items * 0.20
    )

    b_cutoff = math.ceil(
        total_items * 0.50
    )

    classifications = {}

    for index, (key, volume) in enumerate(
        sorted_items
    ):

        rank_percentile = round(
            (
                (index + 1)
                / total_items
            ) * 100,
            2,
        )

        if index < a_cutoff:
            tier = "A"

        elif index < b_cutoff:
            tier = "B"

        else:
            tier = "C"

        classifications[key] = {
            "abc_tier": tier,
            "sales_volume": volume,
            "rank_percentile": rank_percentile,
        }

    return classifications


def calculate_tier_safety_stock(
    base_safety_stock: int,
    abc_tier: str,
) -> int:

    if base_safety_stock < 0:
        raise ValueError(
            "Safety stock cannot be negative"
        )

    if abc_tier == "A":
        multiplier = 1.5

    elif abc_tier == "B":
        multiplier = 1.2

    else:
        multiplier = 1.0

    return int(
        base_safety_stock * multiplier
    )