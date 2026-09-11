from sqlalchemy.orm import Session

from app.models.inventory import Inventory
from app.models.inventory_cost_layer import InventoryCostLayer


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
        raise ValueError("Inventory record not found")

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

    return round(total_value, 2)


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
        raise ValueError("Inventory record not found")

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