import csv
import io

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models.inventory import Inventory
from app.models.sales_history import SalesHistory
from app.schemas.inventory import (
    InventoryCreate,
    InventoryUpdate,
    BulkUpdateItem,
)
from app.services.reorder_service import (
    calculate_reorder_point,
    calculate_urgency_score,
)
from app.services.demand_service import (
    calculate_rolling_average_demand,
)

# =========================================================
# RESPONSE
# =========================================================

def inventory_response(
    inventory: Inventory,
    db: Session,
):
    calculation = calculate_reorder_point(
        db=db,
        inventory=inventory,
    )

    return {
        "sku_id": inventory.sku_id,
        "product_name": inventory.product_name,
        "warehouse_id": inventory.warehouse_id,
        "quantity_on_hand": inventory.quantity_on_hand,
        "reorder_point": calculation["reorder_point"],
        "avg_daily_demand": calculation["rolling_avg_demand"],
        "lead_time_days": inventory.lead_time_days,
        "safety_stock": calculation["adjusted_safety_stock"],
    }


# =========================================================
# CREATE
# =========================================================

def create_inventory(
    db: Session,
    inventory: InventoryCreate,
):
    existing = (
        db.query(Inventory)
        .filter(
            Inventory.sku_id == inventory.sku_id,
            Inventory.warehouse_id == inventory.warehouse_id,
        )
        .first()
    )

    if existing:
        return None

    # Check actual SalesHistory data.
    # If a real negative sale exists, reject the inventory creation.
    negative_sales = (
        db.query(SalesHistory)
        .filter(
            SalesHistory.sku_id == inventory.sku_id,
            SalesHistory.warehouse_id == inventory.warehouse_id,
            SalesHistory.quantity_sold < 0,
        )
        .first()
    )

    if negative_sales:
        raise ValueError(
            "Negative demand data is not allowed"
        )

    item = Inventory(
        sku_id=inventory.sku_id,
        product_name=inventory.product_name,
        warehouse_id=inventory.warehouse_id,
        quantity_on_hand=inventory.quantity_on_hand,
        lead_time_days=inventory.lead_time_days,
        safety_stock=inventory.safety_stock,
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    return item


# =========================================================
# GET ALL
# =========================================================

def get_all_inventory(
    db: Session,
):
    return db.query(Inventory).all()


# =========================================================
# GET SINGLE
# =========================================================

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


# =========================================================
# UPDATE
# =========================================================

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

    update_data = inventory.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(item, field, value)

    db.commit()
    db.refresh(item)

    return item


# =========================================================
# DELETE
# =========================================================

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


# =========================================================
# LOW STOCK
# =========================================================

def get_low_stock_items(
    db: Session,
):
    inventories = db.query(Inventory).all()

    result = []

    for inventory in inventories:
        calculation = calculate_reorder_point(
            db=db,
            inventory=inventory,
        )

        reorder_point = calculation[
            "reorder_point"
        ]

        if inventory.quantity_on_hand >= reorder_point:
            continue

        avg_demand = calculation[
            "rolling_avg_demand"
        ]

        urgency_score = calculate_urgency_score(
            quantity_on_hand=inventory.quantity_on_hand,
            reorder_point=reorder_point,
            avg_daily_demand=avg_demand,
        )

        if urgency_score <= 1:
            urgency_days = 1
        elif urgency_score <= 3:
            urgency_days = 3
        else:
            urgency_days = 5

        result.append(
            {
                "sku_id": inventory.sku_id,
                "product_name": inventory.product_name,
                "warehouse_id": inventory.warehouse_id,
                "quantity_on_hand": inventory.quantity_on_hand,
                "reorder_point": reorder_point,
                "urgency_days": urgency_days,
            }
        )

    return result


# =========================================================
# DEMAND SPIKE / SIMULATION
# =========================================================

def simulate_demand_spike(
    db: Session,
    sku_id: str,
    warehouse_id: str,
    demand_spike_percent: float,
):
    inventory = get_inventory(
        db,
        sku_id,
        warehouse_id,
    )

    if inventory is None:
        return None

    calculation = calculate_reorder_point(
        db=db,
        inventory=inventory,
    )

    current_demand = calculation[
        "rolling_avg_demand"
    ]

    new_demand = current_demand * (
        1 + demand_spike_percent / 100
    )

    new_reorder_point = int(
        new_demand * inventory.lead_time_days
        + inventory.safety_stock
    )

    needs_reorder = (
        inventory.quantity_on_hand
        < new_reorder_point
    )

    suggested_order_qty = max(
        new_reorder_point
        - inventory.quantity_on_hand,
        0,
    )

    return {
        "sku_id": inventory.sku_id,
        "current_quantity": inventory.quantity_on_hand,
        "new_reorder_point": new_reorder_point,
        "needs_reorder": needs_reorder,
        "suggested_order_qty": suggested_order_qty,
    }


# =========================================================
# BULK UPDATE
# =========================================================

def bulk_update_inventory(
    updates: list[BulkUpdateItem],
    db: Session,
):
    updated_items = []

    try:
        for update in updates:
            item = (
                db.query(Inventory)
                .filter(
                    Inventory.sku_id == update.sku_id,
                    Inventory.warehouse_id
                    == update.warehouse_id,
                )
                .first()
            )

            if item is None:
                raise ValueError(
                    f"Inventory not found: "
                    f"{update.sku_id}/"
                    f"{update.warehouse_id}"
                )

            new_quantity = (
                item.quantity_on_hand
                + update.quantity_delta
            )

            if new_quantity < 0:
                raise ValueError(
                    f"Quantity cannot be negative "
                    f"for {update.sku_id}/"
                    f"{update.warehouse_id}"
                )

            item.quantity_on_hand = new_quantity

            updated_items.append(item)

        db.commit()

        for item in updated_items:
            db.refresh(item)

        return updated_items

    except Exception:
        db.rollback()
        raise


# =========================================================
# CSV BULK UPLOAD
# =========================================================

def bulk_upload_csv(
    db: Session,
    file: UploadFile,
):
    content = file.file.read()

    if isinstance(content, bytes):
        content = content.decode("utf-8")

    reader = csv.DictReader(
        io.StringIO(content)
    )

    total_records = 0

    for row in reader:

        sku_id = row["sku_id"]
        warehouse_id = row["warehouse_id"]

        # =====================================================
        # Check existing inventory
        # =====================================================

        existing = get_inventory(
            db,
            sku_id,
            warehouse_id,
        )

        if existing:
            continue

        # =====================================================
        # Get sales history for this SKU + warehouse
        # =====================================================

        sales = (
            db.query(SalesHistory)
            .filter(
                SalesHistory.sku_id == sku_id,
                SalesHistory.warehouse_id == warehouse_id,
            )
            .all()
        )

        # =====================================================
        # Calculate average daily demand automatically
        # =====================================================

        if sales:

            total_sales = sum(
                sale.quantity_sold
                for sale in sales
            )

            sales_days = len(sales)

            avg_daily_demand = round(
                total_sales / sales_days,
                2
            )

        else:

            # No sales history found
            avg_daily_demand = 0.0

        # =====================================================
        # Create inventory
        # =====================================================

        item = Inventory(
            sku_id=sku_id,
            product_name=row["product_name"],
            warehouse_id=warehouse_id,

            quantity_on_hand=int(
                row["quantity_on_hand"]
            ),

            avg_daily_demand=avg_daily_demand,

            lead_time_days=int(
                row["lead_time_days"]
            ),

            safety_stock=int(
                row["safety_stock"]
            ),
        )

        db.add(item)

        total_records += 1

    # =========================================================
    # Save
    # =========================================================

    db.commit()

    return {
        "message": "CSV uploaded successfully",
        "total_records": total_records,
    }

# =========================================================
# WHAT-IF
# =========================================================

def what_if_simulation(
    db: Session,
    spike_percent: float,
):
    inventories = db.query(Inventory).all()

    result = []

    for inventory in inventories:
        calculation = calculate_reorder_point(
            db=db,
            inventory=inventory,
        )

        current_demand = calculation[
            "rolling_avg_demand"
        ]

        new_demand = current_demand * (
            1 + spike_percent / 100
        )

        new_reorder_point = int(
            new_demand
            * inventory.lead_time_days
            + inventory.safety_stock
        )

        needs_reorder = (
            inventory.quantity_on_hand
            < new_reorder_point
        )

        suggested_order_qty = max(
            new_reorder_point
            - inventory.quantity_on_hand,
            0,
        )

        result.append(
            {
                "sku_id": inventory.sku_id,
                "current_quantity": inventory.quantity_on_hand,
                "new_reorder_point": new_reorder_point,
                "needs_reorder": needs_reorder,
                "suggested_order_qty": suggested_order_qty,
            }
        )

    return {
        "spike_percent": spike_percent,
        "total_items": len(result),
        "affected_items": sum(
            1
            for item in result
            if item["needs_reorder"]
        ),
        "total_suggested_order_qty": sum(
            item["suggested_order_qty"]
            for item in result
        ),
        "details": result,
    }