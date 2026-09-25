from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.inventory import Inventory
from app.services import demand_service


def _build_inventory_tree(db: Session):
    inventories = (
        db.query(Inventory)
        .order_by(
            Inventory.sku_id,
            Inventory.warehouse_id,
        )
        .all()
    )

    inventory_map = {}
    children = defaultdict(list)

    for item in inventories:
        key = (
            item.sku_id,
            item.warehouse_id,
        )

        inventory_map[key] = item

        parent_id = item.parent_warehouse_id

        if parent_id:
            children[
                (
                    item.sku_id,
                    parent_id,
                )
            ].append(key)

    return inventory_map, children


def _calculate_downstream_demand(
    sku_id: str,
    warehouse_key,
    children,
    demand_by_location,
    visited=None,
):
    if visited is None:
        visited = set()

    if warehouse_key in visited:
        raise ValueError(
            "Warehouse hierarchy contains a cycle"
        )

    current_visited = set(visited)
    current_visited.add(warehouse_key)

    own_demand = demand_by_location.get(
        warehouse_key,
        0.0,
    )

    total_demand = own_demand

    for child_key in children.get(
        warehouse_key,
        [],
    ):
        total_demand += _calculate_downstream_demand(
            sku_id=sku_id,
            warehouse_key=child_key,
            children=children,
            demand_by_location=demand_by_location,
            visited=current_visited,
        )

    return total_demand
def _get_depth(
    warehouse_key,
    inventory_map,
):
    depth = 0
    current = inventory_map.get(warehouse_key)

    visited = set()

    while current is not None:
        key = (
            current.sku_id,
            current.warehouse_id,
        )

        if key in visited:
            raise ValueError(
                "Warehouse hierarchy contains a cycle"
            )

        visited.add(key)

        parent_id = current.parent_warehouse_id

        if not parent_id:
            break

        parent_key = (
            current.sku_id,
            parent_id,
        )

        current = inventory_map.get(parent_key)
        depth += 1

    return depth


def optimize_network_safety_stock(
    db: Session,
    days: int = 30,
):
    """
    Calculate network-level safety-stock recommendations.

    The existing warehouse safety stock is treated as the
    baseline requirement. Downstream demand is aggregated
    through the hierarchy so parent warehouses can carry
    protection for their dependent warehouses.

    No inventory quantities are changed.
    """

    if days <= 0:
        raise ValueError(
            "Demand window must be greater than zero"
        )

    inventory_map, children = _build_inventory_tree(db)

    if not inventory_map:
        return {
            "demand_window_days": days,
            "total_network_safety_stock": 0,
            "warehouses": [],
        }

    demand = (
        demand_service
        .calculate_rolling_average_demand_all(
            db=db,
            days=days,
        )
    )

    results = []

    for key, inventory in inventory_map.items():
        own_demand = demand.get(
            key,
            0.0,
        )

        downstream_demand = _calculate_downstream_demand(
            sku_id=inventory.sku_id,
            warehouse_key=key,
            children=children,
            demand_by_location=demand,
        )

        depth = _get_depth(
            warehouse_key=key,
            inventory_map=inventory_map,
        )

        lead_time = max(
            inventory.lead_time_days,
            0,
        )

        baseline_safety_stock = max(
            inventory.safety_stock,
            0,
        )

        demand_buffer = (
            downstream_demand
            * lead_time
        )

        optimized_safety_stock = max(
            baseline_safety_stock,
            int(demand_buffer),
        )

        current_stock = max(
            inventory.quantity_on_hand,
            0,
        )

        target_stock = (
            optimized_safety_stock
            + int(downstream_demand * lead_time)
        )

        surplus = max(
            current_stock - target_stock,
            0,
        )

        shortage = max(
            target_stock - current_stock,
            0,
        )

        results.append(
            {
                "sku_id": inventory.sku_id,
                "warehouse_id": inventory.warehouse_id,
                "warehouse_type": inventory.warehouse_type,
                "parent_warehouse_id": (
                    inventory.parent_warehouse_id
                ),
                "hierarchy_depth": depth,
                "own_daily_demand": round(
                    own_demand,
                    2,
                ),
                "downstream_daily_demand": round(
                    downstream_demand,
                    2,
                ),
                "current_safety_stock": (
                    baseline_safety_stock
                ),
                "optimized_safety_stock": (
                    optimized_safety_stock
                ),
                "current_quantity": current_stock,
                "target_quantity": target_stock,
                "surplus_quantity": surplus,
                "shortage_quantity": shortage,
            }
        )

    total_safety_stock = sum(
        item["optimized_safety_stock"]
        for item in results
    )

    return {
        "demand_window_days": days,
        "total_network_safety_stock": (
            total_safety_stock
        ),
        "warehouses": results,
    }