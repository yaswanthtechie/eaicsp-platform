from sqlalchemy.orm import Session

from app.models.inventory import Inventory

from app.services.reorder_service import (
    calculate_reorder_point,
)


def find_transfer_suggestion(
    db: Session,
    destination: Inventory,
    destination_reorder_point: int,
):

    destination_shortage = max(
        destination_reorder_point
        - destination.quantity_on_hand,
        0,
    )

    if destination_shortage <= 0:

        return None

    # =====================================================
    # Find same SKU in other warehouses
    # =====================================================

    source_warehouses = (
        db.query(Inventory)
        .filter(
            Inventory.sku_id
            == destination.sku_id,

            Inventory.warehouse_id
            != destination.warehouse_id,
        )
        .all()
    )

    candidates = []

    # =====================================================
    # Find warehouses with excess
    # =====================================================

    for source in source_warehouses:

        source_calculation = (
            calculate_reorder_point(
                db=db,
                inventory=source,
            )
        )

        source_reorder_point = (
            source_calculation[
                "reorder_point"
            ]
        )

        source_excess = max(
            source.quantity_on_hand
            - source_reorder_point,
            0,
        )

        if source_excess <= 0:
            continue

        transfer_quantity = min(
            source_excess,
            destination_shortage,
        )

        if transfer_quantity > 0:

            candidates.append(
                (
                    source_excess,
                    source,
                    transfer_quantity,
                )
            )

    if not candidates:

        return None

    # Choose source with largest excess.
    candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    source_excess, source, transfer_quantity = (
        candidates[0]
    )

    return {
        "sku_id": destination.sku_id,

        "source_warehouse": (
            source.warehouse_id
        ),

        "destination_warehouse": (
            destination.warehouse_id
        ),

        "transfer_quantity": (
            transfer_quantity
        ),

        "source_excess_quantity": (
            source_excess
        ),

        "destination_shortage_quantity": (
            destination_shortage
        ),

        "recommendation": "TRANSFER",
    }