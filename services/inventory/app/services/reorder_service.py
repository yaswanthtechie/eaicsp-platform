from sqlalchemy.orm import Session

from app.models.inventory import Inventory

from app.services.demand_service import (
    calculate_rolling_average_demand,
)

from app.services.abc_service import (
    classify_skus,
    calculate_tier_safety_stock,
)


def calculate_reorder_point(
    db: Session,
    inventory: Inventory,
    demand_days: int = 30,
):

    if inventory.quantity_on_hand < 0:
        raise ValueError(
            "Quantity cannot be negative"
        )

    if inventory.lead_time_days < 0:
        raise ValueError(
            "Lead time cannot be negative"
        )

    if inventory.safety_stock < 0:
        raise ValueError(
            "Safety stock cannot be negative"
        )

    # =====================================================
    # STEP 1
    # Dynamic rolling demand
    # =====================================================

    rolling_avg_demand = (
        calculate_rolling_average_demand(
            db=db,
            sku_id=inventory.sku_id,
            warehouse_id=inventory.warehouse_id,
            days=demand_days,
        )
    )

    # =====================================================
    # STEP 2
    # ABC classification
    # =====================================================

    classifications = classify_skus(db)

    key = (
        inventory.sku_id,
        inventory.warehouse_id,
    )

    classification = classifications.get(
        key
    )

    if classification is None:

        abc_tier = "C"

    else:

        abc_tier = classification[
            "abc_tier"
        ]

    # =====================================================
    # STEP 3
    # ABC safety stock
    # =====================================================

    adjusted_safety_stock = (
        calculate_tier_safety_stock(
            base_safety_stock=(
                inventory.safety_stock
            ),
            abc_tier=abc_tier,
        )
    )

    # =====================================================
    # STEP 4
    # Dynamic reorder point
    #
    # ROP =
    # demand × lead time + safety stock
    # =====================================================

    reorder_point = int(
        rolling_avg_demand
        * inventory.lead_time_days
        + adjusted_safety_stock
    )

    return {
        "reorder_point": reorder_point,

        "rolling_avg_demand": (
            rolling_avg_demand
        ),

        "abc_tier": abc_tier,

        "adjusted_safety_stock": (
            adjusted_safety_stock
        ),
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
        shortage
        / avg_daily_demand,
        2,
    )