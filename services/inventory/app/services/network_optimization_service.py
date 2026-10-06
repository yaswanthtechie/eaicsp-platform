from collections import defaultdict
from datetime import date, timedelta
from math import ceil, sqrt

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.inventory import Inventory
from app.models.sales_history import SalesHistory
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


def _daily_demand_std_all(
    db: Session,
    days: int,
):
    """
    Standard deviation of daily demand per (sku, warehouse).

    Uses the same window as the rolling average in
    demand_service: from the first sale inside the window
    to today, with days that have no sales counted as zero.
    """

    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    records = (
        db.query(SalesHistory)
        .filter(
            SalesHistory.sale_date >= start_date,
            SalesHistory.sale_date <= end_date,
        )
        .all()
    )

    daily = defaultdict(lambda: defaultdict(float))

    for record in records:
        key = (
            record.sku_id,
            record.warehouse_id,
        )

        daily[key][record.sale_date] += record.quantity_sold

    result = {}

    for key, by_day in daily.items():
        first_day = min(by_day)
        observed_days = (end_date - first_day).days + 1

        values = [
            by_day.get(first_day + timedelta(days=offset), 0.0)
            for offset in range(observed_days)
        ]

        if len(values) < 2:
            result[key] = 0.0
            continue

        mean = sum(values) / len(values)

        result[key] = sqrt(
            sum((value - mean) ** 2 for value in values)
            / (len(values) - 1)
        )

    return result


def _aggregate_downstream(
    warehouse_key,
    children,
    demand_by_location,
    std_by_location,
    visited=None,
):
    """
    Return (daily demand, daily demand variance) for a
    warehouse plus everything below it.

    Demand adds up. Variance also adds up (assuming
    independent locations), so the pooled standard
    deviation sqrt(sum of variances) is smaller than the
    sum of the individual standard deviations. That gap
    is the risk-pooling benefit of holding stock upstream.
    """

    if visited is None:
        visited = set()

    if warehouse_key in visited:
        raise ValueError(
            "Warehouse hierarchy contains a cycle"
        )

    current_visited = set(visited)
    current_visited.add(warehouse_key)

    total_demand = demand_by_location.get(
        warehouse_key,
        0.0,
    )

    total_variance = (
        std_by_location.get(
            warehouse_key,
            0.0,
        )
        ** 2
    )

    for child_key in children.get(
        warehouse_key,
        [],
    ):
        child_demand, child_variance = _aggregate_downstream(
            warehouse_key=child_key,
            children=children,
            demand_by_location=demand_by_location,
            std_by_location=std_by_location,
            visited=current_visited,
        )

        total_demand += child_demand
        total_variance += child_variance

    return total_demand, total_variance


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

    For each warehouse:

        safety stock = z * sigma_pooled * sqrt(lead time)
        target       = safety stock + lead-time demand

    sigma_pooled is the pooled standard deviation of daily
    demand for the warehouse and everything downstream of it.
    z comes from NETWORK_SERVICE_LEVEL_Z (1.65 ~ 95% cycle
    service level). The configured safety_stock is kept as
    a floor.

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
            "service_level_z": settings.NETWORK_SERVICE_LEVEL_Z,
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

    demand_std = _daily_demand_std_all(
        db=db,
        days=days,
    )

    z = settings.NETWORK_SERVICE_LEVEL_Z

    results = []

    for key, inventory in inventory_map.items():
        own_demand = demand.get(
            key,
            0.0,
        )

        downstream_demand, downstream_variance = (
            _aggregate_downstream(
                warehouse_key=key,
                children=children,
                demand_by_location=demand,
                std_by_location=demand_std,
            )
        )

        downstream_std = sqrt(downstream_variance)

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

        statistical_safety_stock = ceil(
            z
            * downstream_std
            * sqrt(lead_time)
        )

        optimized_safety_stock = max(
            baseline_safety_stock,
            statistical_safety_stock,
        )

        lead_time_demand = ceil(
            downstream_demand
            * lead_time
        )

        current_stock = max(
            inventory.quantity_on_hand,
            0,
        )

        target_stock = (
            optimized_safety_stock
            + lead_time_demand
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
                "downstream_demand_std": round(
                    downstream_std,
                    2,
                ),
                "lead_time_demand": lead_time_demand,
                "current_safety_stock": (
                    baseline_safety_stock
                ),
                "statistical_safety_stock": (
                    statistical_safety_stock
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
        "service_level_z": z,
        "total_network_safety_stock": (
            total_safety_stock
        ),
        "warehouses": results,
    }