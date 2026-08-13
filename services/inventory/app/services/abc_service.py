from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.sales_history import SalesHistory


def calculate_sales_volume(
    db: Session,
):

    records = (
        db.query(SalesHistory)
        .all()
    )

    volumes = defaultdict(int)

    for record in records:

        if record.quantity_sold < 0:
            raise ValueError(
                "Negative demand data is not allowed"
            )

        key = (
            record.sku_id,
            record.warehouse_id,
        )

        volumes[key] += record.quantity_sold

    return dict(volumes)


def classify_skus(
    db: Session,
):
    """
    Pareto-style ABC classification.

    A:
        cumulative sales volume <= 20%

    B:
        cumulative sales volume <= 50%

    C:
        remaining items
    """

    volumes = calculate_sales_volume(db)

    if not volumes:
        return {}

    sorted_items = sorted(
        volumes.items(),
        key=lambda item: item[1],
    )

    total_volume = sum(
        volume
        for _, volume in sorted_items
    )

    if total_volume <= 0:

        return {
            key: {
                "sales_volume": volume,
                "abc_tier": "C",
                "cumulative_percentage": 100.0,
            }
            for key, volume in sorted_items
        }

    result = {}

    cumulative_volume = 0

    for key, volume in sorted_items:

        cumulative_volume += volume

        cumulative_percentage = (
            cumulative_volume
            / total_volume
            * 100
        )

        if cumulative_percentage <= 20:
            tier = "A"

        elif cumulative_percentage <= 50:
            tier = "B"

        else:
            tier = "C"

        result[key] = {
            "sales_volume": volume,
            "abc_tier": tier,
            "cumulative_percentage": round(
                cumulative_percentage,
                2,
            ),
        }

    return result


def calculate_tier_safety_stock(
    base_safety_stock: int,
    abc_tier: str,
) -> int:

    if base_safety_stock < 0:
        raise ValueError(
            "Safety stock cannot be negative"
        )

    if abc_tier == "A":

        return int(
            base_safety_stock * 1.50
        )

    if abc_tier == "B":

        return int(
            base_safety_stock * 1.20
        )

    if abc_tier == "C":

        return base_safety_stock

    raise ValueError(
        "Invalid ABC tier"
    )