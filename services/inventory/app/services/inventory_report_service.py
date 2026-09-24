from sqlalchemy.orm import Session

from app.models.inventory import Inventory

from app.services.valuation_service import (
    calculate_fifo_value,
    calculate_weighted_average_value,
)


def generate_inventory_value_report(
    db: Session,
    valuation_method: str = "fifo",
):
    inventories = (
        db.query(Inventory)
        .all()
    )

    # Store the total value for each
    # warehouse + category combination.
    grouped_report = {}

    for inventory in inventories:

        if valuation_method == "fifo":

            value = calculate_fifo_value(
                db=db,
                sku_id=inventory.sku_id,
                warehouse_id=inventory.warehouse_id,
            )

        elif valuation_method == "weighted_average":

            value = calculate_weighted_average_value(
                db=db,
                sku_id=inventory.sku_id,
                warehouse_id=inventory.warehouse_id,
            )

        else:

            raise ValueError(
                "Unsupported valuation method"
            )

        category = inventory.category or "Uncategorized"

        key = (
            inventory.warehouse_id,
            category,
        )

        if key not in grouped_report:
            grouped_report[key] = 0.0

        grouped_report[key] += value

    # Convert grouped values into the response format.
    report = []

    for (warehouse_id, category), inventory_value in grouped_report.items():

        # Don't return zero-value rows.
        if inventory_value == 0:
            continue

        report.append(
            {
                "warehouse_id": warehouse_id,
                "category": category,
                "inventory_value": round(
                    inventory_value,
                    2,
                ),
            }
        )

    total_inventory_value = sum(
        grouped_report.values()
    )

    return {
        "valuation_method": valuation_method,
        "report": report,
        "total_inventory_value": round(
            total_inventory_value,
            2,
        ),
    }