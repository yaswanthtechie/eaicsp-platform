from io import StringIO
import csv

from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.inventory import Inventory
from app.schemas.inventory import (
    InventoryCreate,
    InventoryUpdate,
    BulkUpdateItem,
)


class InventoryOperationError(Exception):
    pass


# ---------------------------------------
# Helper Functions
# ---------------------------------------

def calculate_reorder_point(item: Inventory) -> int:
    return int(
        (item.avg_daily_demand * item.lead_time_days)
        + item.safety_stock
    )


def inventory_response(item: Inventory):

    return {
        "sku_id": item.sku_id,
        "product_name": item.product_name,
        "warehouse_id": item.warehouse_id,
        "quantity_on_hand": item.quantity_on_hand,
        "reorder_point": calculate_reorder_point(item),
        "avg_daily_demand": item.avg_daily_demand,
        "lead_time_days": item.lead_time_days,
        "safety_stock": item.safety_stock,
    }



# ---------------------------------------
# Get Inventory
# ---------------------------------------

def get_inventory(
    db: Session,
    sku_id: str,
    warehouse_id: str,
):

    return (
        db.query(Inventory)
        .filter(
            Inventory.sku_id == sku_id,
            Inventory.warehouse_id == warehouse_id,
        )
        .first()
    )



def get_all_inventory(db: Session):

    items = (
        db.query(Inventory)
        .all()
    )

    return [
        inventory_response(item)
        for item in items
    ]



# ---------------------------------------
# Create Inventory
# ---------------------------------------

def create_inventory(
    db: Session,
    inventory: InventoryCreate,
):

    existing = get_inventory(
        db,
        inventory.sku_id,
        inventory.warehouse_id,
    )

    if existing:
        return None


    item = Inventory(
        sku_id=inventory.sku_id,
        warehouse_id=inventory.warehouse_id,
        product_name=inventory.product_name,
        quantity_on_hand=inventory.quantity_on_hand,
        avg_daily_demand=inventory.avg_daily_demand,
        lead_time_days=inventory.lead_time_days,
        safety_stock=inventory.safety_stock,
    )


    db.add(item)

    db.commit()

    db.refresh(item)


    return inventory_response(item)



# ---------------------------------------
# Update Inventory
# ---------------------------------------

def update_inventory(
    db: Session,
    sku_id: str,
    warehouse_id: str,
    inventory: InventoryUpdate,
):

    item = get_inventory(
        db,
        sku_id,
        warehouse_id,
    )


    if item is None:
        return None


    data = inventory.model_dump(
        exclude_unset=True
    )


    for key, value in data.items():
        setattr(
            item,
            key,
            value
        )


    db.commit()

    db.refresh(item)


    return inventory_response(item)



# ---------------------------------------
# Delete Inventory
# ---------------------------------------

def delete_inventory(
    db: Session,
    sku_id: str,
    warehouse_id: str,
):

    item = get_inventory(
        db,
        sku_id,
        warehouse_id,
    )


    if item is None:
        return False
    
    
    db.delete(item)

    db.commit()


    return True
# ---------------------------------------
# Reorder Check
# ---------------------------------------

def reorder_check(
    db: Session,
    sku_id: str,
    warehouse_id: str,
):

    item = get_inventory(
        db,
        sku_id,
        warehouse_id,
    )


    if item is None:
        return None


    reorder_point = calculate_reorder_point(item)


    return {
        "sku_id": item.sku_id,
        "current_qty": item.quantity_on_hand,
        "reorder_point": reorder_point,
        "needs_reorder":
            item.quantity_on_hand <= reorder_point,
        "suggested_order_qty":
            max(
                0,
                reorder_point - item.quantity_on_hand
            ),
    }



# ---------------------------------------
# Low Stock Items
# ---------------------------------------

def get_low_stock_items(
    db: Session,
):

    items = (
        db.query(Inventory)
        .all()
    )


    result = []


    for item in items:

        reorder_point = calculate_reorder_point(
            item
        )


        if item.quantity_on_hand <= reorder_point:

            result.append(
                {
                    "sku_id": item.sku_id,
                    "product_name": item.product_name,
                    "quantity_on_hand":
                        item.quantity_on_hand,
                    "reorder_point":
                        reorder_point,
                }
            )


    return result



# ---------------------------------------
# Multi Warehouse Reorder Plan
# ---------------------------------------

def get_reorder_plan(
    db: Session,
):

    items = (
        db.query(Inventory)
        .all()
    )


    plan = []


    for item in items:

        reorder_point = calculate_reorder_point(
            item
        )


        if item.avg_daily_demand > 0:

            urgency = (
                reorder_point -
                item.quantity_on_hand
            ) / item.avg_daily_demand

        else:

            urgency = 0



        plan.append(
            {
                "sku_id": item.sku_id,
                "product_name": item.product_name,
                "warehouse_id": item.warehouse_id,
                "quantity_on_hand":
                    item.quantity_on_hand,
                "reorder_point":
                    reorder_point,
                "urgency_score":
                    urgency,
            }
        )


    # Highest urgency first

    plan.sort(
        key=lambda x: x["urgency_score"],
        reverse=True
    )


    return plan



# ---------------------------------------
# Demand Spike Simulation
# ---------------------------------------

def simulate_demand_spike(
    db: Session,
    sku_id: str,
    warehouse_id: str,
    demand_spike_percent: float,
):

    item = get_inventory(
        db,
        sku_id,
        warehouse_id,
    )


    if item is None:
        return None



    new_demand = (
        item.avg_daily_demand *
        (
            1 +
            demand_spike_percent / 100
        )
    )



    new_reorder_point = int(
        (
            new_demand *
            item.lead_time_days
        )
        +
        item.safety_stock
    )



    return {

        "sku_id": item.sku_id,

        "current_quantity":
            item.quantity_on_hand,

        "new_reorder_point":
            new_reorder_point,

        "needs_reorder":
            item.quantity_on_hand
            <= new_reorder_point,


        "suggested_order_qty":
            max(
                0,
                new_reorder_point -
                item.quantity_on_hand
            )
    }



# ---------------------------------------
# What If Simulation
# ---------------------------------------

def what_if_simulation(
    db: Session,
    spike_percent: float,
):

    items = (
        db.query(Inventory)
        .all()
    )


    affected = []


    for item in items:


        new_demand = (
            item.avg_daily_demand *
            (
                1 +
                spike_percent / 100
            )
        )


        new_reorder_point = int(
            (
                new_demand *
                item.lead_time_days
            )
            +
            item.safety_stock
        )


        if item.quantity_on_hand <= new_reorder_point:


            affected.append(
                {
                    "sku_id":
                        item.sku_id,

                    "warehouse_id":
                        item.warehouse_id,

                    "current_quantity":
                        item.quantity_on_hand,

                    "new_reorder_point":
                        new_reorder_point
                }
            )


    return {
        "spike_percent": spike_percent,
        "affected_skus": affected
    }



# ---------------------------------------
# Bulk Update Inventory
# Transaction + Row Locking
# ---------------------------------------

def bulk_update_inventory(items, db):

    try:

        # Always lock rows in same order
        # Prevents PostgreSQL deadlocks
        items = sorted(
            items,
            key=lambda x: (
                x.sku_id,
                x.warehouse_id
            )
        )


        updated_items = []


        for item in items:


            inventory = (
                db.query(Inventory)
                .filter(
                    Inventory.sku_id == item.sku_id,
                    Inventory.warehouse_id == item.warehouse_id
                )
                .with_for_update()
                .first()
            )


            if inventory is None:

                raise HTTPException(
                    status_code=404,
                    detail=f"Inventory not found: {item.sku_id}"
                )


            new_quantity = (
                inventory.quantity_on_hand
                +
                item.quantity_delta
            )


            if new_quantity < 0:

                raise HTTPException(
                    status_code=409,
                    detail="Insufficient inventory quantity"
                )


            inventory.quantity_on_hand = new_quantity


            updated_items.append(
                inventory
            )


        db.commit()


        return [
            inventory_response(item)
            for item in updated_items
        ]


    except HTTPException:

        db.rollback()
        raise


    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ---------------------------------------
# CSV Bulk Upload
# ---------------------------------------

def bulk_upload_csv(
    db: Session,
    file: UploadFile,
):


    if not file.filename.endswith(".csv"):

        raise HTTPException(
            status_code=400,
            detail="Only CSV files allowed"
        )


    try:

        content = (
            file.file
            .read()
            .decode("utf-8")
        )


    except Exception:

        raise HTTPException(
            status_code=400,
            detail="Invalid CSV file"
        )



    reader = csv.DictReader(
        StringIO(content)
    )


    required_columns = {

        "sku_id",
        "product_name",
        "warehouse_id",
        "quantity_on_hand",
        "avg_daily_demand",
        "lead_time_days",
        "safety_stock",

    }



    if reader.fieldnames is None:

        raise HTTPException(
            status_code=400,
            detail="Empty CSV"
        )



    missing = (
        required_columns
        -
        set(reader.fieldnames)
    )


    if missing:

        raise HTTPException(
            status_code=400,
            detail=
            f"Missing columns {missing}"
        )



    inserted = 0



    try:


        for row in reader:
            
            existing = get_inventory(
                db,
                row["sku_id"],
                row["warehouse_id"],
            )



            if existing:

                raise HTTPException(
                    status_code=409,
                    detail=
                    f"Duplicate SKU "
                    f"{row['sku_id']} "
                    f"in warehouse "
                    f"{row['warehouse_id']}"
                )



            item = Inventory(

                sku_id=
                    row["sku_id"],

                warehouse_id=
                    row["warehouse_id"],

                product_name=
                    row["product_name"],

                quantity_on_hand=
                    int(
                        row["quantity_on_hand"]
                    ),

                avg_daily_demand=
                    float(
                        row["avg_daily_demand"]
                    ),

                lead_time_days=
                    int(
                        row["lead_time_days"]
                    ),

                safety_stock=
                    int(
                        row["safety_stock"]
                    ),
            )


            db.add(item)

            inserted += 1



        db.commit()



        return {

            "message":
                "CSV uploaded successfully",

            "total_records":
                inserted
        }



    except Exception:

        db.rollback()

        raise