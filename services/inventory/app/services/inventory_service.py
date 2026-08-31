import csv
import io

from fastapi import UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.inventory import Inventory
from app.schemas.inventory import (
    InventoryCreate,
)
from app.services.reorder_service import (
    build_reorder_context,
    calculate_reorder_point,
    calculate_urgency_score,
)


MAX_UPLOAD_BYTES = 5 * 1024 * 1024

REQUIRED_CSV_COLUMNS = (
    "sku_id",
    "product_name",
    "warehouse_id",
    "quantity_on_hand",
    "lead_time_days",
    "safety_stock",
)


# =========================================================
# RESPONSE
# =========================================================

def inventory_response(
    inventory: Inventory,
    db: Session,
):
    """
    Build the response for one inventory item.

    Demand is calculated dynamically from sales history.
    ABC classification is used to adjust safety stock.
    """

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
        "avg_daily_demand": calculation[
            "rolling_avg_demand"
        ],
        "lead_time_days": inventory.lead_time_days,
        "safety_stock": calculation[
            "adjusted_safety_stock"
        ],
    }


# =========================================================
# CREATE
# =========================================================

def create_inventory(
    db: Session,
    inventory,
):
    """
    Create one inventory record.

    IMPORTANT:
    Return the SQLAlchemy Inventory object.
    The route is responsible for building the response.
    """

    existing = get_inventory(
        db=db,
        sku_id=inventory.sku_id,
        warehouse_id=inventory.warehouse_id,
    )

    if existing:
        raise ValueError(
            "Inventory already exists"
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

    try:
        # Make the INSERT available to this transaction.
        db.flush()

        # This is intentionally called before commit.
        #
        # If sales history contains negative demand,
        # reorder calculation should raise ValueError.
        inventory_response(
            inventory=item,
            db=db,
        )

        # Commit only when all calculations succeed.
        db.commit()

    except Exception:
        db.rollback()
        raise

    return item


# =========================================================
# GET ALL
# =========================================================

def get_all_inventory(
    db: Session,
):
    return (
        db.query(Inventory)
        .all()
    )


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
    inventory,
):
    """
    Update an existing inventory record.

    The parameter name is `inventory` because the route calls:

        update_inventory(
            db=db,
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            inventory=inventory,
        )
    """

    item = get_inventory(
        db=db,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
    )

    if item is None:
        return None

    update_data = inventory.model_dump(
        exclude_unset=True
    )

    # avg_daily_demand is calculated from sales history.
    # It must never be manually changed.
    update_data.pop(
        "avg_daily_demand",
        None,
    )

    for field, value in update_data.items():

        # Only update fields that actually exist
        # on the Inventory model.
        if hasattr(item, field):
            setattr(
                item,
                field,
                value,
            )

    try:
        db.flush()

        # Recalculate dynamic values after update.
        inventory_response(
            inventory=item,
            db=db,
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

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
        db=db,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
    )

    if item is None:
        return False

    try:
        db.delete(item)
        db.commit()

    except Exception:
        db.rollback()
        raise

    return True


# =========================================================
# LOW STOCK
# =========================================================

def get_low_stock_items(
    db: Session,
):
    inventories = (
        db.query(Inventory)
        .all()
    )

    if not inventories:
        return []

    # Calculate shared demand / ABC information once.
    context = build_reorder_context(
        db=db,
    )

    result = []

    for inventory in inventories:

        calculation = calculate_reorder_point(
            db=db,
            inventory=inventory,
            context=context,
        )

        reorder_point = calculation[
            "reorder_point"
        ]

        # At ROP = no reorder.
        if (
            inventory.quantity_on_hand
            >= reorder_point
        ):
            continue

        avg_demand = calculation[
            "rolling_avg_demand"
        ]

        urgency_score = calculate_urgency_score(
            quantity_on_hand=(
                inventory.quantity_on_hand
            ),
            reorder_point=reorder_point,
            avg_daily_demand=avg_demand,
        )

        # Convert urgency score to urgency days.
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
                "quantity_on_hand": (
                    inventory.quantity_on_hand
                ),
                "reorder_point": reorder_point,
                "urgency_days": urgency_days,
            }
        )

    return result


# =========================================================
# SINGLE SKU SIMULATION
# =========================================================

def simulate_demand_spike(
    db: Session,
    sku_id: str,
    warehouse_id: str,
    demand_spike_percent: float,
):
    inventory = get_inventory(
        db=db,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
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

    adjusted_safety_stock = calculation[
        "adjusted_safety_stock"
    ]

    new_demand = (
        current_demand
        * (1 + demand_spike_percent / 100)
    )

    new_reorder_point = int(
        new_demand
        * inventory.lead_time_days
        + adjusted_safety_stock
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
        "current_quantity": (
            inventory.quantity_on_hand
        ),
        "new_reorder_point": new_reorder_point,
        "needs_reorder": needs_reorder,
        "suggested_order_qty": (
            suggested_order_qty
        ),
    }


# =========================================================
# BULK UPDATE
# =========================================================

def bulk_update_inventory(
    updates,
    db: Session,
):
    """
    Atomically update multiple inventory rows.

    PostgreSQL row locking prevents lost updates during
    concurrent operations.
    """

    updated_items = []

    # Always acquire locks in the same order.
    ordered_updates = sorted(
        updates,
        key=lambda update: (
            update.sku_id,
            update.warehouse_id,
        ),
    )

    try:

        for update in ordered_updates:

            item = (
                db.query(Inventory)
                .filter(
                    Inventory.sku_id
                    == update.sku_id,
                    Inventory.warehouse_id
                    == update.warehouse_id,
                )
                .with_for_update()
                .first()
            )

            if item is None:
                raise ValueError(
                    "Inventory not found for "
                    f"{update.sku_id}/"
                    f"{update.warehouse_id}"
                )

            new_quantity = (
                item.quantity_on_hand
                + update.quantity_delta
            )

            if new_quantity < 0:
                raise ValueError(
                    "Inventory quantity cannot "
                    "be negative for "
                    f"{update.sku_id}/"
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
    content = file.file.read(
        MAX_UPLOAD_BYTES + 1
    )

    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError(
            "File is larger than the 5MB limit"
        )

    if isinstance(content, bytes):

        try:
            content = content.decode("utf-8")

        except UnicodeDecodeError:
            raise ValueError(
                "File must be a UTF-8 encoded CSV"
            )

    reader = csv.DictReader(
        io.StringIO(content)
    )

    if reader.fieldnames is None:
        raise ValueError(
            "CSV file is empty"
        )

    missing_columns = [
        column
        for column in REQUIRED_CSV_COLUMNS
        if column not in reader.fieldnames
    ]

    if missing_columns:
        raise ValueError(
            "CSV is missing required "
            "column(s): "
            + ", ".join(missing_columns)
        )

    new_items = []
    seen_keys = set()

    for row_number, row in enumerate(
        reader,
        start=2,
    ):

        try:
            parsed = InventoryCreate(
                **{
                    column: row[column]
                    for column in REQUIRED_CSV_COLUMNS
                }
            )

        except ValidationError as exc:

            first = exc.errors()[0]

            field = (
                first["loc"][0]
                if first["loc"]
                else "row"
            )

            raise ValueError(
                f"Row {row_number}: "
                f"{field} - "
                f"{first['msg']}"
            )

        key = (
            parsed.sku_id,
            parsed.warehouse_id,
        )

        if key in seen_keys:
            raise ValueError(
                f"Row {row_number}: duplicate "
                f"entry for "
                f"{parsed.sku_id}/"
                f"{parsed.warehouse_id}"
            )

        seen_keys.add(key)

        existing = get_inventory(
            db=db,
            sku_id=parsed.sku_id,
            warehouse_id=parsed.warehouse_id,
        )

        if existing:
            continue

        new_items.append(
            Inventory(
                sku_id=parsed.sku_id,
                product_name=parsed.product_name,
                warehouse_id=parsed.warehouse_id,
                quantity_on_hand=(
                    parsed.quantity_on_hand
                ),
                lead_time_days=(
                    parsed.lead_time_days
                ),
                safety_stock=(
                    parsed.safety_stock
                ),
            )
        )

    try:

        db.add_all(new_items)
        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "message": "CSV uploaded successfully",
        "total_records": len(new_items),
    }


# =========================================================
# WHAT-IF SIMULATION
# =========================================================

def what_if_simulation(
    db: Session,
    spike_percent: float,
):
    """
    Simulate demand growth without modifying inventory.
    """

    inventories = (
        db.query(Inventory)
        .all()
    )

    if not inventories:
        return {
            "spike_percent": spike_percent,
            "total_items": 0,
            "affected_items": 0,
            "total_suggested_order_qty": 0,
            "details": [],
        }

    context = build_reorder_context(
        db=db,
    )

    result = []

    for inventory in inventories:

        calculation = calculate_reorder_point(
            db=db,
            inventory=inventory,
            context=context,
        )

        current_demand = calculation[
            "rolling_avg_demand"
        ]

        adjusted_safety_stock = calculation[
            "adjusted_safety_stock"
        ]

        new_demand = (
            current_demand
            * (1 + spike_percent / 100)
        )

        new_reorder_point = int(
            new_demand
            * inventory.lead_time_days
            + adjusted_safety_stock
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
                "current_quantity": (
                    inventory.quantity_on_hand
                ),
                "new_reorder_point": (
                    new_reorder_point
                ),
                "needs_reorder": needs_reorder,
                "suggested_order_qty": (
                    suggested_order_qty
                ),
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
