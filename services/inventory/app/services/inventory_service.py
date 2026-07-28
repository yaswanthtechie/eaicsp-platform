from sqlalchemy.orm import Session
from fastapi import UploadFile, HTTPException
from io import StringIO
import csv

from app.models.inventory import Inventory
from app.schemas.inventory import InventoryCreate, InventoryUpdate


def calculate_reorder_point(item):
    return int(
        (item.avg_daily_demand * item.lead_time_days)
        + item.safety_stock
    )


def inventory_response(item):
    return {
        "sku_id": item.sku_id,
        "product_name": item.product_name,
        "warehouse_id": item.warehouse_id,
        "quantity_on_hand": item.quantity_on_hand,
        "reorder_point": calculate_reorder_point(item),
        "safety_stock": item.safety_stock,
        "lead_time_days": item.lead_time_days,
        "avg_daily_demand": item.avg_daily_demand,
    }


def get_inventory(db: Session, sku_id: str):
    return (
        db.query(Inventory)
        .filter(Inventory.sku_id == sku_id)
        .first()
    )


def create_inventory(db: Session, inventory: InventoryCreate):

    existing = get_inventory(db, inventory.sku_id)

    if existing:
        return None

    item = Inventory(
        sku_id=inventory.sku_id,
        product_name=inventory.product_name,
        warehouse_id=inventory.warehouse_id,
        quantity_on_hand=inventory.quantity_on_hand,
        safety_stock=inventory.safety_stock,
        lead_time_days=inventory.lead_time_days,
        avg_daily_demand=inventory.avg_daily_demand,
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    return inventory_response(item)


def get_all_inventory(db: Session):

    items = db.query(Inventory).all()

    return [
        inventory_response(item)
        for item in items
    ]


def update_inventory(
    db: Session,
    sku_id: str,
    inventory: InventoryUpdate,
):

    item = get_inventory(db, sku_id)

    if item is None:
        return None

    update_data = inventory.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(item, key, value)

    db.commit()
    db.refresh(item)

    return inventory_response(item)


def delete_inventory(
    db: Session,
    sku_id: str,
):

    item = get_inventory(db, sku_id)

    if item is None:
        return False

    db.delete(item)
    db.commit()

    return True


def reorder_check(
    db: Session,
    sku_id: str,
):

    item = get_inventory(db, sku_id)

    if item is None:
        return None

    reorder_point = calculate_reorder_point(item)

    needs_reorder = (
        item.quantity_on_hand <= reorder_point
    )

    suggested_order_qty = max(
        0,
        reorder_point - item.quantity_on_hand
    )

    return {
        "sku_id": item.sku_id,
        "current_qty": item.quantity_on_hand,
        "reorder_point": reorder_point,
        "needs_reorder": needs_reorder,
        "suggested_order_qty": suggested_order_qty,
    }


def get_low_stock_items(db: Session):

    items = db.query(Inventory).all()

    result = []

    for item in items:

        reorder_point = calculate_reorder_point(item)

        if item.quantity_on_hand <= reorder_point:

            result.append({
                "sku_id": item.sku_id,
                "product_name": item.product_name,
                "quantity_on_hand": item.quantity_on_hand,
                "reorder_point": reorder_point,
            })

    return result


def simulate_demand_spike(
    db: Session,
    sku_id: str,
    demand_spike_percent: float,
):

    item = get_inventory(db, sku_id)

    if item is None:
        return None

    new_avg_daily_demand = (
        item.avg_daily_demand
        * (1 + demand_spike_percent / 100)
    )

    new_reorder_point = int(
        (new_avg_daily_demand * item.lead_time_days)
        + item.safety_stock
    )

    needs_reorder = (
        item.quantity_on_hand <= new_reorder_point
    )

    suggested_order_qty = max(
        0,
        new_reorder_point - item.quantity_on_hand
    )

    return {
        "sku_id": item.sku_id,
        "current_quantity": item.quantity_on_hand,
        "new_reorder_point": new_reorder_point,
        "needs_reorder": needs_reorder,
        "suggested_order_qty": suggested_order_qty,
    }


def bulk_upload_csv(
    db: Session,
    file: UploadFile,
):

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are allowed",
        )

    try:
        contents = file.file.read().decode("utf-8")
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Unable to read CSV file.",
        )

    reader = csv.DictReader(StringIO(contents))

    required_columns = {
        "sku_id",
        "product_name",
        "warehouse_id",
        "quantity_on_hand",
        "safety_stock",
        "lead_time_days",
        "avg_daily_demand",
    }

    if reader.fieldnames is None:
        raise HTTPException(
            status_code=400,
            detail="CSV file is empty.",
        )

    missing = required_columns - set(reader.fieldnames)

    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing columns: {', '.join(sorted(missing))}",
        )

    inserted = 0

    try:

        for row_number, row in enumerate(reader, start=2):

            existing = get_inventory(
                db,
                row["sku_id"].strip(),
            )

            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Row {row_number}: SKU already exists.",
                )

            item = Inventory(
                sku_id=row["sku_id"].strip(),
                product_name=row["product_name"].strip(),
                warehouse_id=row["warehouse_id"].strip(),
                quantity_on_hand=int(row["quantity_on_hand"]),
                safety_stock=int(row["safety_stock"]),
                lead_time_days=int(row["lead_time_days"]),
                avg_daily_demand=float(row["avg_daily_demand"]),
            )

            db.add(item)
            inserted += 1

        db.commit()

        return {
            "message": "CSV uploaded successfully",
            "total_records": inserted,
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"CSV upload failed: {str(e)}",
        )