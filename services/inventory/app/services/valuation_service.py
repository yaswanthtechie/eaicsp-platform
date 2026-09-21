from datetime import datetime

from sqlalchemy.orm import Session

from app.models.inventory import Inventory
from app.models.inventory_cost_layer import InventoryCostLayer


# ==========================================================
# CONSUME COST LAYERS
# ==========================================================
# When inventory leaves a warehouse, consume the oldest
# available cost layers first.
#
# Example:
#
# 10 units @ $5
# 10 units @ $10
#
# Remove 12 units:
#
# 10 units @ $5  -> consumed
# 2 units @ $10  -> consumed
#
# Remaining:
#
# 8 units @ $10
# ==========================================================

def consume_cost_layers(
    db: Session,
    sku_id: str,
    warehouse_id: str,
    quantity: int,
) -> list[tuple[int, float]]:

    if quantity <= 0:
        return []

    layers = (
        db.query(InventoryCostLayer)
        .filter(
            InventoryCostLayer.sku_id == sku_id,
            InventoryCostLayer.warehouse_id == warehouse_id,
            InventoryCostLayer.quantity_remaining > 0,
        )
        .order_by(
            InventoryCostLayer.received_at.asc()
        )
        .with_for_update()
        .all()
    )

    remaining = quantity

    consumed = []

    for layer in layers:

        if remaining <= 0:
            break

        take = min(
            remaining,
            layer.quantity_remaining,
        )

        layer.quantity_remaining -= take

        remaining -= take

        consumed.append(
            (
                take,
                layer.unit_cost,
            )
        )

    return consumed


# ==========================================================
# ADD COST LAYER
# ==========================================================
# Adds inventory cost information to a warehouse.
#
# Used when:
# - stock is received
# - stock is transferred into another warehouse
# - bulk inventory quantity increases and a known cost exists
# ==========================================================

def add_cost_layer(
    db: Session,
    sku_id: str,
    warehouse_id: str,
    category: str,
    quantity: int,
    unit_cost: float,
    received_at: datetime | None = None,
) -> None:

    if quantity <= 0:
        return

    db.add(
        InventoryCostLayer(
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            category=category,
            quantity_received=quantity,
            quantity_remaining=quantity,
            unit_cost=unit_cost,
            received_at=(
                received_at
                or datetime.utcnow()
            ),
        )
    )


# ==========================================================
# LATEST UNIT COST
# ==========================================================
# Returns the most recently received unit cost.
#
# Used when bulk inventory quantity increases and the
# application needs a cost for the newly added quantity.
# ==========================================================

def latest_unit_cost(
    db: Session,
    sku_id: str,
    warehouse_id: str,
) -> float | None:

    layer = (
        db.query(InventoryCostLayer)
        .filter(
            InventoryCostLayer.sku_id == sku_id,
            InventoryCostLayer.warehouse_id == warehouse_id,
        )
        .order_by(
            InventoryCostLayer.received_at.desc()
        )
        .first()
    )

    if layer is None:
        return None

    return layer.unit_cost


# ==========================================================
# FIFO VALUATION
# ==========================================================

def calculate_fifo_value(
    db: Session,
    sku_id: str,
    warehouse_id: str,
) -> float:

    inventory = (
        db.query(Inventory)
        .filter(
            Inventory.sku_id == sku_id,
            Inventory.warehouse_id == warehouse_id,
        )
        .first()
    )

    if inventory is None:
        raise ValueError(
            "Inventory record not found"
        )

    quantity_needed = inventory.quantity_on_hand

    if quantity_needed <= 0:
        return 0.0

    layers = (
        db.query(InventoryCostLayer)
        .filter(
            InventoryCostLayer.sku_id == sku_id,
            InventoryCostLayer.warehouse_id == warehouse_id,
            InventoryCostLayer.quantity_remaining > 0,
        )
        .order_by(
            InventoryCostLayer.received_at.asc()
        )
        .all()
    )

    total_value = 0.0

    for layer in layers:

        if quantity_needed <= 0:
            break

        quantity_from_layer = min(
            quantity_needed,
            layer.quantity_remaining,
        )

        total_value += (
            quantity_from_layer
            * layer.unit_cost
        )

        quantity_needed -= quantity_from_layer

    return round(
        total_value,
        2,
    )


# ==========================================================
# WEIGHTED AVERAGE VALUATION
# ==========================================================

def calculate_weighted_average_value(
    db: Session,
    sku_id: str,
    warehouse_id: str,
) -> float:

    inventory = (
        db.query(Inventory)
        .filter(
            Inventory.sku_id == sku_id,
            Inventory.warehouse_id == warehouse_id,
        )
        .first()
    )

    if inventory is None:
        raise ValueError(
            "Inventory record not found"
        )

    current_quantity = inventory.quantity_on_hand

    if current_quantity <= 0:
        return 0.0

    layers = (
        db.query(InventoryCostLayer)
        .filter(
            InventoryCostLayer.sku_id == sku_id,
            InventoryCostLayer.warehouse_id == warehouse_id,
            InventoryCostLayer.quantity_remaining > 0,
        )
        .all()
    )

    total_quantity = 0
    total_cost = 0.0

    for layer in layers:

        total_quantity += (
            layer.quantity_remaining
        )

        total_cost += (
            layer.quantity_remaining
            * layer.unit_cost
        )

    if total_quantity == 0:
        return 0.0

    weighted_average_cost = (
        total_cost / total_quantity
    )

    inventory_value = (
        current_quantity
        * weighted_average_cost
    )

    return round(
        inventory_value,
        2,
    )