from sqlalchemy.orm import Session

from app.models.inventory import Inventory
from app.services import demand_service
from app.services.abc_service import (
    classify_skus,
    calculate_tier_safety_stock,
)


ROLLING_WINDOW_DAYS = 30


def build_reorder_context(
    db: Session,
    demand_days: int = ROLLING_WINDOW_DAYS,
):
    inventories = (
        db.query(Inventory)
        .all()
    )

    inventory_by_sku = {}

    for item in inventories:
        inventory_by_sku.setdefault(
            item.sku_id,
            [],
        ).append(item)

    demand = (
        demand_service
        .calculate_rolling_average_demand_all(
            db=db,
            days=demand_days,
        )
    )

    classifications = classify_skus(db)

    return {
        "demand": demand,
        "classifications": classifications,
        "inventory_by_sku": inventory_by_sku,
        "demand_days": demand_days,
    }


def calculate_reorder_point(
    db: Session,
    inventory,
    demand_days: int = ROLLING_WINDOW_DAYS,
    context=None,
):
    def get_value(obj, name):

        if hasattr(obj, name):
            return getattr(obj, name)

        if hasattr(obj, "model_dump"):
            data = obj.model_dump()

            if name in data:
                return data[name]

        if isinstance(obj, dict):
            if name in obj:
                return obj[name]

        raise TypeError(
            "calculate_reorder_point() requires "
            f"inventory data containing '{name}'"
        )

    sku_id = get_value(
        inventory,
        "sku_id",
    )

    warehouse_id = get_value(
        inventory,
        "warehouse_id",
    )

    quantity_on_hand = get_value(
        inventory,
        "quantity_on_hand",
    )

    lead_time_days = get_value(
        inventory,
        "lead_time_days",
    )

    safety_stock = get_value(
        inventory,
        "safety_stock",
    )

    if quantity_on_hand < 0:
        raise ValueError(
            "Quantity cannot be negative"
        )

    if lead_time_days < 0:
        raise ValueError(
            "Lead time cannot be negative"
        )

    if safety_stock < 0:
        raise ValueError(
            "Safety stock cannot be negative"
        )

    key = (
        sku_id,
        warehouse_id,
    )

    if context is None:

        rolling_avg_demand = (
            demand_service
            .calculate_rolling_average_demand(
                db=db,
                sku_id=sku_id,
                warehouse_id=warehouse_id,
                days=demand_days,
            )
        )

    else:

        rolling_avg_demand = (
            context["demand"].get(
                key,
                0.0,
            )
        )

    if rolling_avg_demand is None:
        rolling_avg_demand = 0.0

    if rolling_avg_demand < 0:
        raise ValueError(
            "Demand cannot be negative"
        )

    if context is None:
        classifications = classify_skus(db)
    else:
        classifications = (
            context["classifications"]
        )

    classification = classifications.get(
        key
    )

    abc_tier = (
        classification["abc_tier"]
        if classification
        else "C"
    )

    adjusted_safety_stock = (
        calculate_tier_safety_stock(
            base_safety_stock=safety_stock,
            abc_tier=abc_tier,
        )
    )

    reorder_point = int(
        rolling_avg_demand
        * lead_time_days
        + adjusted_safety_stock
    )

    return {
        "reorder_point": reorder_point,
        "rolling_avg_demand": rolling_avg_demand,
        "abc_tier": abc_tier,
        "adjusted_safety_stock": adjusted_safety_stock,
    }


def calculate_urgency_score(
    quantity_on_hand: int,
    reorder_point: int,
    avg_daily_demand: float,
):
    if quantity_on_hand < 0:
        raise ValueError(
            "Quantity cannot be negative"
        )

    if reorder_point < 0:
        raise ValueError(
            "Reorder point cannot be negative"
        )

    if avg_daily_demand < 0:
        raise ValueError(
            "Demand cannot be negative"
        )

    if quantity_on_hand >= reorder_point:
        return 0.0

    shortage = (
        reorder_point
        - quantity_on_hand
    )

    if avg_daily_demand == 0:
        return float(shortage)

    return round(
        shortage / avg_daily_demand,
        2,
    )