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
    Find a warehouse with excess stock for the same SKU.

    When the destination belongs to a configured warehouse
    hierarchy, only its upstream parent warehouses are used.

    When no parent warehouse is configured, retain the
    existing same-SKU behavior for backward compatibility.
    """

    destination_shortage = max(
        destination_reorder_point
        - destination.quantity_on_hand,
        0,
    )

    if destination_shortage <= 0:
        return None

    # -----------------------------------------------------
    # LOAD SAME-SKU INVENTORY
    # -----------------------------------------------------

    if context is not None:
        source_warehouses = (
            context["inventory_by_sku"].get(
                destination.sku_id,
                [],
            )
        )
    else:
        source_warehouses = (
            db.query(Inventory)
            .filter(
                Inventory.sku_id
                == destination.sku_id,
            )
            .all()
        )

    source_warehouses = [
        item
        for item in source_warehouses
        if item.warehouse_id
        != destination.warehouse_id
    ]

    # -----------------------------------------------------
    # FIND UPSTREAM PARENT CHAIN
    # -----------------------------------------------------

    inventory_by_warehouse = {}

    for item in source_warehouses:
        inventory_by_warehouse[
            item.warehouse_id
        ] = item

    parent_chain = []

    current = destination

    visited_warehouse_ids = {
        destination.warehouse_id
    }

    while current.parent_warehouse_id:

        parent = inventory_by_warehouse.get(
            current.parent_warehouse_id
        )

        if parent is None:
            break

        if parent.warehouse_id in visited_warehouse_ids:
            raise ValueError(
                "Warehouse hierarchy contains a cycle at "
                f"{parent.warehouse_id}. "
                "Fix parent_warehouse_id "
                "for this SKU."
            )

        visited_warehouse_ids.add(
            parent.warehouse_id
        )

        parent_chain.append(parent)

        current = parent

    # -----------------------------------------------------
    # SOURCE SELECTION
    #
    # If hierarchy exists:
    #     use only upstream warehouses.
    #
    # If hierarchy does not exist:
    #     preserve existing behavior and consider
    #     other warehouses with the same SKU.
    # -----------------------------------------------------

    if parent_chain:
        source_warehouses = parent_chain

    candidates = []

    for source in source_warehouses:

        source_calculation = calculate_reorder_point(
            db=db,
            inventory=source,
            context=context,
        )

        source_reorder_point = int(
            source_calculation["reorder_point"]
        )

        source_excess = max(
            source.quantity_on_hand
            - source_reorder_point,
            0,
        )

        if source_excess <= 0:
            continue

        if (
            source.lead_time_days
            > destination.lead_time_days
        ):
            continue

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

        if parent_chain:
            hierarchy_distance = (
                parent_chain.index(source)
                + 1
            )
        else:
            hierarchy_distance = 999

        candidates.append(
            {
                "source": source,
                "source_excess": source_excess,
                "transfer_quantity": transfer_quantity,
                "days_saved": days_saved,
                "hierarchy_distance": (
                    hierarchy_distance
                ),
            }
        )

    if not candidates:
        return None

    # -----------------------------------------------------
    # SELECT BEST SOURCE
    # -----------------------------------------------------

    if parent_chain:
        candidates.sort(
            key=lambda item: (
                item["hierarchy_distance"],
                -item["days_saved"],
                -item["source_excess"],
            )
        )
    else:
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