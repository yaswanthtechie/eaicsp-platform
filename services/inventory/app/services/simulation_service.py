from sqlalchemy.orm import Session

from app.models.inventory import Inventory
from app.services.reorder_service import (
    build_reorder_context,
    calculate_reorder_point,
)


def simulate_demand_growth(
    db: Session,
    growth_percent: float = 30.0,
):
    if growth_percent < 0:
        raise ValueError(
            "Growth percentage cannot be negative"
        )

    inventories = (
        db.query(Inventory)
        .all()
    )

    if not inventories:
        return {
            "growth_percent": growth_percent,
            "total_inventory_items": 0,
            "total_current_daily_demand": 0.0,
            "total_simulated_daily_demand": 0.0,
            "additional_daily_demand": 0.0,
            "items": [],
        }

    context = build_reorder_context(
        db=db,
    )

    result = []

    total_current_demand = 0.0
    total_simulated_demand = 0.0

    for inventory in inventories:

        calculation = calculate_reorder_point(
            db=db,
            inventory=inventory,
            context=context,
        )

        current_demand = calculation[
            "rolling_avg_demand"
        ]

        adjusted_safety_stock = calculation[
            "adjusted_safety_stock"
        ]

        simulated_demand = (
            current_demand
            * (1 + growth_percent / 100)
        )

        simulated_reorder_point = int(
            simulated_demand
            * inventory.lead_time_days
            + adjusted_safety_stock
        )

        current_reorder_point = calculation[
            "reorder_point"
        ]

        needs_reorder = (
            inventory.quantity_on_hand
            < simulated_reorder_point
        )

        suggested_order_qty = max(
            simulated_reorder_point
            - inventory.quantity_on_hand,
            0,
        )

        total_current_demand += current_demand
        total_simulated_demand += (
            simulated_demand
        )

        result.append(
            {
                "sku_id": inventory.sku_id,
                "warehouse_id": inventory.warehouse_id,
                "current_quantity": (
                    inventory.quantity_on_hand
                ),
                "current_demand": current_demand,
                "simulated_demand": simulated_demand,
                "current_reorder_point": (
                    current_reorder_point
                ),
                "simulated_reorder_point": (
                    simulated_reorder_point
                ),
                "needs_reorder": needs_reorder,
                "suggested_order_qty": (
                    suggested_order_qty
                ),
            }
        )

    return {
        "growth_percent": growth_percent,
        "total_inventory_items": len(result),
        "total_current_daily_demand": (
            total_current_demand
        ),
        "total_simulated_daily_demand": (
            total_simulated_demand
        ),
        "additional_daily_demand": (
            total_simulated_demand
            - total_current_demand
        ),
        "items": result,
    }