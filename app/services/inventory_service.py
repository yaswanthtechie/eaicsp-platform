from fastapi import HTTPException, UploadFile
from sqlalchemy import and_, select, tuple_, update 
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import csv
from io import StringIO

from app.models.inventory import Inventory
from app.schemas.inventory import BulkUpdateItem, InventoryCreate, InventoryUpdate


class InventoryOperationError(Exception):
    pass


def calculate_reorder_point(item: Inventory) -> float:
    return item.avg_daily_demand * item.lead_time_days + item.safety_stock


def inventory_response(item: Inventory):
    return {"sku_id": item.sku_id,
            "product_name": item.product_name,
            "warehouse_id": item.warehouse_id,
            "quantity_on_hand": item.quantity_on_hand,
            "reorder_point": calculate_reorder_point(item), 
            "safety_stock": item.safety_stock,
            "lead_time_days": item.lead_time_days,
            "avg_daily_demand": item.avg_daily_demand
            }


def get_inventory(db: Session, sku_id: str, warehouse_id: str):
    return db.execute(select(Inventory).where(and_(Inventory.sku_id == sku_id, Inventory.warehouse_id == warehouse_id))).scalar_one_or_none()


def get_inventory_locations(db: Session, sku_id: str):
    return db.execute(select(Inventory).where(Inventory.sku_id == sku_id)).scalars().all()


def create_inventory(db: Session, inventory: InventoryCreate):
    item = Inventory(**inventory.model_dump())
    try:
        db.add(item); db.commit(); db.refresh(item)
        return inventory_response(item)
    except IntegrityError:
        db.rollback(); 
        return None


def get_all_inventory(db: Session):
    return [inventory_response(item) for item in db.execute(select(Inventory)).scalars()]


def update_inventory(db: Session, sku_id: str, warehouse_id: str, inventory: InventoryUpdate):
    item = get_inventory(db, sku_id, warehouse_id)
    if item is None: return None
    for key, value in inventory.model_dump(exclude_unset=True).items(): setattr(item, key, value)
    db.commit(); db.refresh(item)
    return inventory_response(item)


def delete_inventory(db: Session, sku_id: str, warehouse_id: str):
    item = get_inventory(db, sku_id, warehouse_id)
    if item is None: return False
    db.delete(item); db.commit(); return True
 

def reorder_check(db: Session, sku_id: str, warehouse_id: str):
    item = get_inventory(db, sku_id, warehouse_id)
    if item is None: return None
    point = calculate_reorder_point(item)
    row = inventory_response(item)
    row.update({"current_qty": item.quantity_on_hand, "needs_reorder": item.quantity_on_hand <= point,
                "suggested_order_qty": max(0, int(point - item.quantity_on_hand))})
    return row


def get_reorder_plan(db: Session):
    plan = []
    for item in db.execute(select(Inventory)).scalars():
        point = calculate_reorder_point(item)
        if item.quantity_on_hand <= point:
            row = reorder_check(db, item.sku_id, item.warehouse_id)
            row["urgency_score"] = (point - item.quantity_on_hand) / item.avg_daily_demand
            row["days_until_stockout"] = item.quantity_on_hand / item.avg_daily_demand
            plan.append(row)
    return sorted(plan, key=lambda row: row["urgency_score"], reverse=True)


def get_low_stock_items(db: Session):
    """Original low-stock response shape, retained for existing clients."""
    result = []
    for item in db.execute(select(Inventory)).scalars():
        point = calculate_reorder_point(item)
        if item.quantity_on_hand <= point:
            result.append({"sku_id": item.sku_id, "product_name": item.product_name,
                           "warehouse_id": item.warehouse_id,
                           "quantity_on_hand": item.quantity_on_hand,
                           "reorder_point": point})
    return result


def bulk_update_inventory(db: Session, changes: list[BulkUpdateItem]):
    if not changes:
        raise InventoryOperationError("updates must contain at least one item")
    keys = sorted((change.sku_id, change.warehouse_id) for change in changes)
    if len(keys) != len(set(keys)):
        raise InventoryOperationError("each SKU/warehouse may appear only once")
    try:
        with db.begin():
            if db.bind.dialect.name != "sqlite":
                locked = db.execute(select(Inventory).where(tuple_(Inventory.sku_id, Inventory.warehouse_id).in_(keys)).order_by(Inventory.sku_id, Inventory.warehouse_id).with_for_update()).scalars().all()
                if {(item.sku_id, item.warehouse_id) for item in locked} != set(keys):
                    raise InventoryOperationError("one or more inventory rows do not exist")
            result = []
            for change in changes:
                statement = update(Inventory).where(and_(Inventory.sku_id == change.sku_id, Inventory.warehouse_id == change.warehouse_id)).where(Inventory.quantity_on_hand + change.quantity_delta >= 0).values(quantity_on_hand=Inventory.quantity_on_hand + change.quantity_delta).returning(Inventory)
                item = db.execute(statement).scalar_one_or_none()
                if item is None: raise InventoryOperationError(f"insufficient stock for {change.sku_id} at {change.warehouse_id}")
                result.append(item)
        return [inventory_response(item) for item in result]
    except Exception:
        db.rollback(); raise


def simulate_demand_spike(db: Session, spike_percent: float):
    results = []
    multiplier = 1 + spike_percent / 100
    for item in db.execute(select(Inventory)).scalars():
        point = item.avg_daily_demand * multiplier * item.lead_time_days + item.safety_stock
        if item.quantity_on_hand <= point:
            row = inventory_response(item)
            row.update({"spike_percent": spike_percent, "spiked_avg_daily_demand": item.avg_daily_demand * multiplier,
                        "spiked_reorder_point": point, "needs_reorder": True})
            results.append(row)
    return results


def simulate_single_demand_spike(db: Session, item: Inventory, spike_percent: float):
    """Former per-SKU simulation response, retained for API compatibility."""
    new_avg_daily_demand = item.avg_daily_demand * (1 + spike_percent / 100)
    point = new_avg_daily_demand * item.lead_time_days + item.safety_stock
    return {"sku_id": item.sku_id, "current_quantity": item.quantity_on_hand,
            "new_reorder_point": point, "needs_reorder": item.quantity_on_hand <= point,
            "suggested_order_qty": max(0, int(point - item.quantity_on_hand))}


def bulk_upload_csv(db: Session, file: UploadFile):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Only CSV files are allowed")
    try:
        rows = list(csv.DictReader(StringIO(file.file.read().decode("utf-8"))))
        with db.begin():
            for row in rows: db.add(Inventory(**row))
        return {"message": "CSV uploaded successfully", "total_records": len(rows)}
    except Exception as exc:
        db.rollback(); raise HTTPException(400, f"CSV upload failed: {exc}") from exc
