from sqlalchemy.orm import Session

from app.models.inventory import Inventory
from app.services.reorder_service import calculate_reorder_point


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

    multiplier = (
        1 + growth_percent / 100
    )

    items = []

    total_current_demand = 0.0
    total_simulated_demand = 0.0
    total_current_rop = 0
    total_simulated_rop = 0

    currently_low_stock = 0
    simulated_low_stock = 0
    additional_reorder_items = 0

    for inventory in inventories:

        calculation = calculate_reorder_point(
            db=db,
            inventory=inventory,
        )

        current_demand = float(
            calculation["rolling_avg_demand"]
        )

        if current_demand < 0:
            raise ValueError(
                f"Negative demand for "
                f"{inventory.sku_id}/"
                f"{inventory.warehouse_id}"
            )

        simulated_demand = (
            current_demand * multiplier
        )

        current_rop = int(
            calculation["reorder_point"]
        )

        simulated_rop = int(
            simulated_demand
            * inventory.lead_time_days
            + calculation[
                "adjusted_safety_stock"
            ]
        )

        current_low = (
            inventory.quantity_on_hand
            < current_rop
        )

        simulated_low = (
            inventory.quantity_on_hand
            < simulated_rop
        )

        if current_low:
            currently_low_stock += 1

        if simulated_low:
            simulated_low_stock += 1

        if not current_low and simulated_low:
            additional_reorder_items += 1

        total_current_demand += current_demand
        total_simulated_demand += simulated_demand
        total_current_rop += current_rop
        total_simulated_rop += simulated_rop

        items.append(
            {
                "sku_id": inventory.sku_id,
                "product_name": inventory.product_name,
                "warehouse_id": inventory.warehouse_id,
                "quantity_on_hand": (
                    inventory.quantity_on_hand
                ),
                "current_daily_demand": round(
                    current_demand,
                    2,
                ),
                "simulated_daily_demand": round(
                    simulated_demand,
                    2,
                ),
                "current_reorder_point": (
                    current_rop
                ),
                "simulated_reorder_point": (
                    simulated_rop
                ),
                "currently_low_stock": current_low,
                "low_stock_after_simulation": (
                    simulated_low
                ),
            }
        )

    return {
        "scenario": (
            f"Demand increases by "
            f"{growth_percent}%"
        ),
        "growth_percent": growth_percent,
        "total_inventory_items": len(
            inventories
        ),
        "currently_low_stock_items": (
            currently_low_stock
        ),
        "low_stock_items_after_simulation": (
            simulated_low_stock
        ),
        "additional_reorder_items": (
            additional_reorder_items
        ),
        "total_current_daily_demand": round(
            total_current_demand,
            2,
        ),
        "total_simulated_daily_demand": round(
            total_simulated_demand,
            2,
        ),
        "additional_daily_demand": round(
            total_simulated_demand
            - total_current_demand,
            2,
        ),
        "total_current_reorder_point": (
            total_current_rop
        ),
        "total_simulated_reorder_point": (
            total_simulated_rop
        ),
        "additional_reorder_point": (
            total_simulated_rop
            - total_current_rop
        ),
        "items": items,
    }