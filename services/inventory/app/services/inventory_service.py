import csv
import io

from fastapi import HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.inventory import Inventory
from app.schemas.inventory import (
    InventoryCreate,
    InventoryUpdate,
)
from app.services.reorder_service import (
    build_reorder_context,
    calculate_reorder_point,
    calculate_urgency_score,
)
from app.services.purchase_order_service import (
    create_draft_po_for_inventory,
)
from app.services.valuation_service import (
    add_cost_layer,
    consume_cost_layers,
    latest_unit_cost,
)


MAX_UPLOAD_BYTES = 5 * 1024 * 1024

REQUIRED_CSV_COLUMNS = (
    "sku_id",
    "product_name",
    "warehouse_id",
    "category",
    "quantity_on_hand",
    "lead_time_days",
    "safety_stock",
    "warehouse_type",
    "parent_warehouse_id",
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
        "category": inventory.category,
        "quantity_on_hand": inventory.quantity_on_hand,
        "reorder_point": calculation[
            "reorder_point"
        ],
        "avg_daily_demand": calculation[
            "rolling_avg_demand"
        ],
        "lead_time_days": inventory.lead_time_days,
        "safety_stock": calculation[
            "adjusted_safety_stock"
        ],
        "warehouse_type": inventory.warehouse_type,
        "parent_warehouse_id": (
            inventory.parent_warehouse_id
        ),
        "version": inventory.version,
    }


# =========================================================
# AUTOMATIC M2 PURCHASE ORDER
# =========================================================

def generate_draft_po_if_required(
    db: Session,
    inventory: Inventory,
):
    """
    Automatically generate a draft purchase order
    when the inventory quantity is below its reorder point.

    The purchase_order_service handles:
    - reorder-point validation
    - suggested quantity
    - cheapest supplier selection
    - unit cost
    - expected cost
    - duplicate draft-PO prevention

    Returns:
        PurchaseOrder object when a PO is created/existing.
        None when reorder is not required.
    """

    return create_draft_po_for_inventory(
        db=db,
        inventory=inventory,
    )


# =========================================================
# CREATE
# =========================================================

def create_inventory(
    db: Session,
    inventory,
):
    """
    Create one inventory record.

    The service returns the SQLAlchemy Inventory object.
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

    # -----------------------------------------------------
    # MILESTONE 1:
    # A warehouse cannot be its own parent.
    # -----------------------------------------------------

    if (
        inventory.parent_warehouse_id
        and inventory.parent_warehouse_id == inventory.warehouse_id
    ):
        raise ValueError(
            "parent_warehouse_id cannot be the warehouse itself"
        )

    item = Inventory(
        sku_id=inventory.sku_id,
        product_name=inventory.product_name,
        warehouse_id=inventory.warehouse_id,
        category=inventory.category,
        quantity_on_hand=inventory.quantity_on_hand,
        lead_time_days=inventory.lead_time_days,
        safety_stock=inventory.safety_stock,
        warehouse_type=inventory.warehouse_type,
        parent_warehouse_id=inventory.parent_warehouse_id,
    )

    db.add(item)

    try:
        db.flush()

        # -------------------------------------------------
        # MILESTONE 3:
        # Opening stock gets a cost layer.
        # -------------------------------------------------

        if item.quantity_on_hand > 0:

            opening_unit_cost = inventory.unit_cost

            if opening_unit_cost is None:
                opening_unit_cost = latest_unit_cost(
                    db=db,
                    sku_id=item.sku_id,
                    warehouse_id=item.warehouse_id,
                )

            if opening_unit_cost is not None:
                add_cost_layer(
                    db=db,
                    sku_id=item.sku_id,
                    warehouse_id=item.warehouse_id,
                    category=item.category,
                    quantity=item.quantity_on_hand,
                    unit_cost=opening_unit_cost,
                )

        # -------------------------------------------------
        # MILESTONE 2:
        # Validate reorder/demand logic before committing.
        #
        # This ensures invalid demand data cannot leave
        # behind a partially-created inventory record.
        # -------------------------------------------------

        try:
            generate_draft_po_if_required(
                db=db,
                inventory=item,
            )
        except ValueError as exc:
            message = str(exc)

            if "Negative demand" in message:
                raise

            # Supplier configuration may be missing.
            # Inventory creation should still succeed.
            pass

        db.commit()
        db.refresh(item)

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
    inventory: InventoryUpdate,
):
    item = (
        db.query(Inventory)
        .filter(
            Inventory.sku_id == sku_id,
            Inventory.warehouse_id == warehouse_id,
        )
        .with_for_update()
        .first()
    )

    if item is None:
        return None

    # -----------------------------------------------------
    # MILESTONE 4:
    # OPTIMISTIC LOCKING
    # -----------------------------------------------------

    if item.version != inventory.version:
        raise HTTPException(
            status_code=409,
            detail=(
                "Inventory record was modified by another user. "
                f"Current version is {item.version}, "
                f"but the request used version {inventory.version}. "
                "Refresh the inventory record and try again."
            ),
        )

    data = inventory.model_dump(
        exclude_unset=True,
        exclude={"version"},
    )

    # -----------------------------------------------------
    # MILESTONE 1:
    # Prevent self-parent configuration.
    # -----------------------------------------------------

    if (
        data.get("parent_warehouse_id")
        == warehouse_id
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "parent_warehouse_id cannot be "
                "the warehouse itself"
            ),
        )

    old_quantity = item.quantity_on_hand

    if "quantity_on_hand" in data:
        new_quantity = data["quantity_on_hand"]

        if new_quantity < 0:
            raise HTTPException(
                status_code=400,
                detail="Quantity cannot be negative",
            )
    else:
        new_quantity = old_quantity

    quantity_delta = (
        new_quantity - old_quantity
    )

    # -----------------------------------------------------
    # Apply normal field updates.
    # -----------------------------------------------------

    for key, value in data.items():
        setattr(
            item,
            key,
            value,
        )

    try:
        # -------------------------------------------------
        # MILESTONE 3:
        # Stock leaving the warehouse consumes FIFO layers.
        # -------------------------------------------------

        if quantity_delta < 0:

            quantity_removed = abs(
                quantity_delta
            )

            consumed = consume_cost_layers(
                db=db,
                sku_id=sku_id,
                warehouse_id=warehouse_id,
                quantity=quantity_removed,
            )

            consumed_quantity = sum(
                quantity
                for quantity, _unit_cost in consumed
            )

            if consumed_quantity != quantity_removed:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Insufficient cost-layer quantity "
                        f"for {sku_id}/{warehouse_id}. "
                        "Cannot decrease inventory without "
                        "matching cost layers."
                    ),
                )

        # -------------------------------------------------
        # MILESTONE 3:
        # Stock entering the warehouse gets a new layer.
        # -------------------------------------------------

        elif quantity_delta > 0:

            unit_cost = latest_unit_cost(
                db=db,
                sku_id=sku_id,
                warehouse_id=warehouse_id,
            )

            if unit_cost is not None:
                add_cost_layer(
                    db=db,
                    sku_id=sku_id,
                    warehouse_id=warehouse_id,
                    category=item.category,
                    quantity=quantity_delta,
                    unit_cost=unit_cost,
                )

        # -------------------------------------------------
        # MILESTONE 4:
        # Increment version after validations succeed.
        # -------------------------------------------------

        item.version += 1

        db.commit()
        db.refresh(item)

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise

    # -----------------------------------------------------
    # MILESTONE 2:
    # Automatic draft PO generation after the inventory
    # update has successfully committed.
    #
    # This is intentionally outside the inventory transaction.
    # -----------------------------------------------------

    try:
        generate_draft_po_if_required(
            db=db,
            inventory=item,
        )
    except ValueError:
        # Inventory update must not fail only because a
        # supplier is unavailable or no supplier exists.
        pass

    return inventory_response(
        item,
        db,
    )


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

        # At exactly ROP there is no reorder.
        if inventory.quantity_on_hand >= reorder_point:
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
        "suggested_order_qty": suggested_order_qty,
    }


# =========================================================
# BULK UPDATE
# =========================================================

def bulk_update_inventory(
    updates: list,
    db: Session,
):
    """
    Atomically update multiple inventory rows.

    PostgreSQL row-level locking prevents lost updates.
    Updates are locked in deterministic order to reduce
    deadlock risk.

    Cost layers are updated together with inventory quantity:
    - decrease -> consume FIFO layers
    - increase -> add a layer using latest known unit cost
    """

    updated_items = []

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

            old_quantity = item.quantity_on_hand

            new_quantity = (
                old_quantity
                + update.quantity_delta
            )

            if new_quantity < 0:
                raise ValueError(
                    "Inventory quantity cannot be "
                    "negative for "
                    f"{update.sku_id}/"
                    f"{update.warehouse_id}"
                )

            # -------------------------------------------------
            # MILESTONE 3:
            # Handle cost layers before changing quantity.
            # -------------------------------------------------

            if update.quantity_delta < 0:

                quantity_removed = abs(
                    update.quantity_delta
                )

                consumed = consume_cost_layers(
                    db=db,
                    sku_id=update.sku_id,
                    warehouse_id=update.warehouse_id,
                    quantity=quantity_removed,
                )

                consumed_quantity = sum(
                    quantity
                    for quantity, _unit_cost in consumed
                )

                if consumed_quantity != quantity_removed:
                    raise ValueError(
                        "Insufficient cost-layer quantity "
                        "for "
                        f"{update.sku_id}/"
                        f"{update.warehouse_id}"
                    )

            elif update.quantity_delta > 0:

                unit_cost = latest_unit_cost(
                    db=db,
                    sku_id=update.sku_id,
                    warehouse_id=update.warehouse_id,
                )

                if unit_cost is not None:
                    add_cost_layer(
                        db=db,
                        sku_id=update.sku_id,
                        warehouse_id=update.warehouse_id,
                        category=item.category,
                        quantity=update.quantity_delta,
                        unit_cost=unit_cost,
                    )

            item.quantity_on_hand = new_quantity

            item.version += 1

            updated_items.append(item)

        # -----------------------------------------------------
        # Commit only after every inventory item succeeds.
        # -----------------------------------------------------

        db.commit()

        for item in updated_items:
            db.refresh(item)

    except Exception:
        db.rollback()
        raise

    # -----------------------------------------------------
    # MILESTONE 2:
    # Generate draft POs only after the complete bulk
    # inventory transaction has succeeded.
    # -----------------------------------------------------

    for item in updated_items:
        try:
            generate_draft_po_if_required(
                db=db,
                inventory=item,
            )
        except ValueError:
            # Do not invalidate the successful bulk inventory
            # update because supplier data is unavailable.
            pass

    return updated_items


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
            "CSV is missing required column(s): "
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

        # -----------------------------------------------------
        # Prevent CSV self-parent records.
        # -----------------------------------------------------

        if (
            parsed.parent_warehouse_id
            and parsed.parent_warehouse_id
            == parsed.warehouse_id
        ):
            raise ValueError(
                f"Row {row_number}: "
                "parent_warehouse_id cannot be "
                "the warehouse itself"
            )

        key = (
            parsed.sku_id,
            parsed.warehouse_id,
        )

        if key in seen_keys:
            raise ValueError(
                f"Row {row_number}: duplicate entry "
                f"for {parsed.sku_id}/"
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
                category=parsed.category,
                quantity_on_hand=(
                    parsed.quantity_on_hand
                ),
                lead_time_days=(
                    parsed.lead_time_days
                ),
                safety_stock=(
                    parsed.safety_stock
                ),
                warehouse_type=(
                    parsed.warehouse_type
                ),
                parent_warehouse_id=(
                    parsed.parent_warehouse_id
                ),
            )
        )

    try:

        db.add_all(new_items)
        db.commit()

    except Exception:
        db.rollback()
        raise

    # -----------------------------------------------------
    # MILESTONE 2:
    # Automatically generate draft POs for newly uploaded
    # inventory records that are already below ROP.
    # -----------------------------------------------------

    for item in new_items:
        try:
            generate_draft_po_if_required(
                db=db,
                inventory=item,
            )
        except ValueError:
            pass

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

    No purchase orders are created here because this is
    intentionally a read-only simulation.
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