from sqlalchemy.orm import Session

from app.models.inventory import Inventory
from app.services.reorder_service import (
    calculate_reorder_point,
)


def find_transfer_suggestion(
    db: Session,
    destination: Inventory,
    destination_reorder_point: int,
    context=None,
):
    """
    Find a warehouse with excess stock of the same SKU
    that can transfer inventory to the destination warehouse.

    A transfer is suggested when:

    1. Destination is below its reorder point.
    2. Another warehouse has the same SKU.
    3. Source has stock above its own reorder point.
    4. Source lead time is not slower than destination lead time.
    """

    # -----------------------------------------------------
    # DESTINATION SHORTAGE
    # -----------------------------------------------------

    destination_shortage = max(
        destination_reorder_point
        - destination.quantity_on_hand,
        0,
    )

    if destination_shortage <= 0:
        return None

    # -----------------------------------------------------
    # FIND OTHER WAREHOUSES WITH SAME SKU
    # -----------------------------------------------------

    if context is not None:
        source_warehouses = [
            item
        for item in context["inventory_by_sku"].get(destination.sku_id, [])
        if item.warehouse_id != destination.warehouse_id
        ]
    else:
        source_warehouses = (
        db.query(Inventory)
        .filter(
            Inventory.sku_id == destination.sku_id,
            Inventory.warehouse_id != destination.warehouse_id,
        )
        .all()
    )

    candidates = []

    # -----------------------------------------------------
    # CHECK EACH SOURCE WAREHOUSE
    # -----------------------------------------------------

    for source in source_warehouses:

        source_calculation = calculate_reorder_point(
            db=db,
            inventory=source,
            context=context,
        )

        source_reorder_point = int(
            source_calculation["reorder_point"]
        )

        # -------------------------------------------------
        # SOURCE EXCESS STOCK
        # -------------------------------------------------

        source_excess = max(
            source.quantity_on_hand
            - source_reorder_point,
            0,
        )

        if source_excess <= 0:
            continue

        # -------------------------------------------------
        # LEAD TIME CHECK
        # -------------------------------------------------

        if (
            source.lead_time_days
            > destination.lead_time_days
        ):
            continue

        # -------------------------------------------------
        # TRANSFER QUANTITY
        # -------------------------------------------------

        transfer_quantity = min(
            source_excess,
            destination_shortage,
        )

        if transfer_quantity <= 0:
            continue

        days_saved = (
            destination.lead_time_days
            - source.lead_time_days
        )

        candidates.append(
            {
                "source": source,
                "source_excess": source_excess,
                "transfer_quantity": transfer_quantity,
                "days_saved": days_saved,
            }
        )

    # -----------------------------------------------------
    # NO VALID SOURCE
    # -----------------------------------------------------

    if not candidates:
        return None

    # -----------------------------------------------------
    # BEST SOURCE
    # -----------------------------------------------------
    #
    # Priority:
    # 1. Most days saved
    # 2. Most excess stock
    #

    candidates.sort(
        key=lambda item: (
            item["days_saved"],
            item["source_excess"],
        ),
        reverse=True,
    )

    best = candidates[0]

    source = best["source"]

    return {
        "sku_id": destination.sku_id,
        "source_warehouse": source.warehouse_id,
        "destination_warehouse": (
            destination.warehouse_id
        ),
        "transfer_quantity": (
            best["transfer_quantity"]
        ),
        "source_excess_quantity": (
            best["source_excess"]
        ),
        "destination_shortage_quantity": (
            destination_shortage
        ),
        "recommendation": "TRANSFER",
        "days_saved_vs_reorder": (
            best["days_saved"]
        ),
    }