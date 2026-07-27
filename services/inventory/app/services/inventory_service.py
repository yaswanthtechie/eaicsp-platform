from app.schemas.inventory import InventoryCreate, InventoryUpdate
from app.models.inventory import Inventory
from sqlalchemy.orm import Session
import csv
from io import StringIO
from fastapi import UploadFile, HTTPException

def create_inventory(db: Session, inventory: InventoryCreate):
    existing_inventory = get_inventory(db, inventory.sku_id)

    if existing_inventory is not None:
        return None

    db_inventory = Inventory(
        sku_id=inventory.sku_id,
        product_name=inventory.product_name,
        warehouse_id=inventory.warehouse_id,
        quantity_on_hand=inventory.quantity_on_hand,
        safety_stock=inventory.safety_stock,
        lead_time_days=inventory.lead_time_days,
        avg_daily_demand=inventory.avg_daily_demand
    )
    db.add(db_inventory)
    db.commit()
    db.refresh(db_inventory)
    return db_inventory


def get_inventory(db: Session, sku_id: str):
    return db.query(Inventory).filter(Inventory.sku_id == sku_id).first()


def get_all_inventory(db: Session):
    return db.query(Inventory).all()


def update_inventory(db: Session, sku_id: str, inventory: InventoryUpdate):
    db_inventory = db.query(Inventory).filter(Inventory.sku_id == sku_id).first()
    if not db_inventory:
        return None

    if inventory.product_name is not None:
        db_inventory.product_name = inventory.product_name
    if inventory.warehouse_id is not None:
        db_inventory.warehouse_id = inventory.warehouse_id
    if inventory.quantity_on_hand is not None:
        db_inventory.quantity_on_hand = inventory.quantity_on_hand
    if inventory.avg_daily_demand is not None:
        db_inventory.avg_daily_demand = inventory.avg_daily_demand
    if inventory.lead_time_days is not None:
        db_inventory.lead_time_days = inventory.lead_time_days
    if inventory.safety_stock is not None:
        db_inventory.safety_stock = inventory.safety_stock

    db.commit()
    db.refresh(db_inventory)
    return db_inventory


def delete_inventory(db: Session, sku_id: str):
    db_inventory = get_inventory(db, sku_id)
    if db_inventory is None:
        return False
    db.delete(db_inventory)
    db.commit()
    return True


def reorder_check(db: Session, sku_id: str):
    db_inventory = get_inventory(db, sku_id)

    if db_inventory is None:
        return None

    reorder_point = (
        db_inventory.avg_daily_demand
        * db_inventory.lead_time_days
    ) + db_inventory.safety_stock

    needs_reorder = (
        db_inventory.quantity_on_hand <= reorder_point
    )

    suggested_order_qty = max(
        0,
        int(reorder_point * 2 - db_inventory.quantity_on_hand)
    )

    return {
        "sku_id": db_inventory.sku_id,
        "current_qty": db_inventory.quantity_on_hand,
        "reorder_point": reorder_point,
        "needs_reorder": needs_reorder,
        "suggested_order_qty": suggested_order_qty,
    }


def calculate_reorder_point(db_inventory):
    return (db_inventory.avg_daily_demand * db_inventory.lead_time_days) + db_inventory.safety_stock


def get_low_stock_items(db: Session):
    db_inventory = db.query(Inventory).all()
    if not db_inventory:
        return []

    low_stock_items = []
    for item in db_inventory:
        reorder_point = calculate_reorder_point(item)
        if item.quantity_on_hand <= reorder_point:
            low_stock_items.append({
                "sku_id": item.sku_id,
                "product_name": item.product_name,
                "current_qty": item.quantity_on_hand,
                "reorder_point": reorder_point,
            })
    return low_stock_items


def simulate_demand_spike(db: Session, sku_id: str, demand_spike_percent: float):
    db_inventory = (
        db.query(Inventory)
        .filter(Inventory.sku_id == sku_id)
        .first()
    )

    if db_inventory is None:
        return None

    new_avg_daily_demand = (
        db_inventory.avg_daily_demand
        * (1 + demand_spike_percent / 100)
    )

    reorder_point = (
        new_avg_daily_demand
        * db_inventory.lead_time_days
    ) + db_inventory.safety_stock

    needs_reorder = (
        db_inventory.quantity_on_hand <= reorder_point
    )

    suggested_order_qty = max(
        0,
        int((reorder_point * 2) - db_inventory.quantity_on_hand)
    )

    return {
        "sku_id": db_inventory.sku_id,
        "product_name": db_inventory.product_name,
        "current_qty": db_inventory.quantity_on_hand,
        "original_avg_daily_demand": db_inventory.avg_daily_demand,
        "demand_spike_percent": demand_spike_percent,
        "new_avg_daily_demand": new_avg_daily_demand,
        "reorder_point": reorder_point,
        "needs_reorder": needs_reorder,
        "suggested_order_qty": suggested_order_qty,
    }
    


def bulk_upload_csv(
    db: Session,
    file: UploadFile
):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are allowed"
        )

    try:
        contents = file.file.read().decode("utf-8")
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Unable to read CSV file."
        )

    csv_reader = csv.DictReader(StringIO(contents))

    required_columns = {
        "sku_id",
        "product_name",
        "warehouse_id",
        "quantity_on_hand",
        
        "safety_stock",
        "lead_time_days",
        "avg_daily_demand"
    }

    if csv_reader.fieldnames is None:
        raise HTTPException(
            status_code=400,
            detail="CSV file is empty."
        )

    missing_columns = required_columns - set(csv_reader.fieldnames)

    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail=f"Missing columns: {', '.join(sorted(missing_columns))}"
        )

    inserted = []

    try:
        for row_number, row in enumerate(csv_reader, start=2):

            # Required field validation
            for column in required_columns:
                value = row.get(column)

                if value is None or value.strip() == "":
                    raise HTTPException(
                        status_code=400,
                        detail=f"Row {row_number}: '{column}' cannot be empty."
                    )

            # Duplicate SKU validation
            existing = (
                db.query(Inventory)
                .filter(Inventory.sku_id == row["sku_id"])
                .first()
            )

            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Row {row_number}: SKU '{row['sku_id']}' already exists."
                )

            try:
                quantity = int(row["quantity_on_hand"])
                
                safety_stock = int(row["safety_stock"])
                lead_time = int(row["lead_time_days"])
                avg_daily_demand = float(row["avg_daily_demand"])
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Row {row_number}: Numeric fields contain invalid values."
                )

            item = Inventory(
                sku_id=row["sku_id"].strip(),
                product_name=row["product_name"].strip(),
                warehouse_id=row["warehouse_id"].strip(),
                quantity_on_hand=quantity,
                safety_stock=safety_stock,
                lead_time_days=lead_time,
                avg_daily_demand=avg_daily_demand
            )

            db.add(item)
            inserted.append(row["sku_id"])

        db.commit()

        return {
            "message": "CSV uploaded successfully",
            "total_records": len(inserted),
            "items_added": inserted
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"CSV upload failed: {str(e)}"
        )