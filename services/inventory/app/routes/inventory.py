
import logging
import time

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core.auth import (
    require_permission,
    require_roles,
)
from app.database import get_db
from app.models.inventory import Inventory
from app.services.network_optimization_service import (
    optimize_network_safety_stock,
)

from app.schemas.inventory import (
    InventoryCreate,
    InventoryUpdate,
    InventoryResponse,
    ReorderCheckResponse,
    LowStockResponse,
    DemandSpikeRequest,
    SimulationResponse,
    DeleteResponse,
    BulkUploadResponse,
    BulkUpdateItem,
    ReorderPlanEntry,
    WhatIfRequest,
    WhatIfResponse,
    MultiEchelonResponse,
)

from app.services.inventory_service import (
    create_inventory,
    get_all_inventory,
    get_inventory,
    update_inventory,
    delete_inventory,
    get_low_stock_items,
    simulate_demand_spike,
    bulk_upload_csv,
    bulk_update_inventory,
    what_if_simulation,
    inventory_response,
    generate_draft_po_if_required,
)

from app.services.reorder_service import (
    build_reorder_context,
    calculate_reorder_point,
    calculate_urgency_score,
)

from app.services.transfer_service import (
    find_transfer_suggestion,
)

from app.services.simulation_service import (
    simulate_demand_growth,
)

from app.services.multi_echelon_service import (
    fulfill_shortage,
)

from app.services.valuation_service import (
    consume_cost_layers,
)


logger = logging.getLogger(__name__)

router = APIRouter()


# =========================================================
# CREATE INVENTORY
# Permission: inventory:write
# =========================================================

@router.post(
    "",
    response_model=InventoryResponse,
    status_code=201,
    dependencies=[
        Depends(require_permission("inventory:write"))
    ],
)
def create_inventory_route(
    inventory: InventoryCreate,
    db: Session = Depends(get_db),
):
    try:
        result = create_inventory(
            db=db,
            inventory=inventory,
        )

        if result is None:
            raise HTTPException(
                status_code=409,
                detail="SKU already exists in warehouse",
            )

        return inventory_response(
            inventory=result,
            db=db,
        )

    except HTTPException:
        raise

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# =========================================================
# GET ALL INVENTORY
# Permission: inventory:read
# =========================================================

@router.get(
    "",
    response_model=list[InventoryResponse],
    dependencies=[
        Depends(require_permission("inventory:read"))
    ],
)
def get_all_inventory_route(
    db: Session = Depends(get_db),
):
    items = get_all_inventory(db)

    return [
        inventory_response(
            inventory=item,
            db=db,
        )
        for item in items
    ]


# =========================================================
# REORDER PLAN
# Permission: inventory:read
# =========================================================

@router.get(
    "/reorder-plan",
    response_model=list[ReorderPlanEntry],
    dependencies=[
        Depends(require_permission("inventory:read"))
    ],
)
def reorder_plan(
    db: Session = Depends(get_db),
):
    try:
        inventories = (
            db.query(Inventory)
            .all()
        )

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

            reorder_point = calculation["reorder_point"]

            # At the reorder point inventory is still sufficient.
            # Reorder only when quantity is below ROP.
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

            transfer = find_transfer_suggestion(
                db=db,
                destination=inventory,
                destination_reorder_point=reorder_point,
                context=context,
            )

            result.append(
                {
                    "sku_id": inventory.sku_id,
                    "product_name": inventory.product_name,
                    "warehouse_id": inventory.warehouse_id,
                    "quantity_on_hand": inventory.quantity_on_hand,
                    "reorder_point": reorder_point,
                    "urgency_score": urgency_score,
                    "rolling_avg_demand": avg_demand,
                    "abc_tier": calculation["abc_tier"],
                    "adjusted_safety_stock": calculation[
                        "adjusted_safety_stock"
                    ],
                    "transfer_suggestion": transfer,
                }
            )

        result.sort(
            key=lambda item: item["urgency_score"],
            reverse=True,
        )

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid inventory data: {exc}",
        )


# =========================================================
# LOW STOCK
# Permission: inventory:read
# =========================================================

@router.get(
    "/low-stock",
    response_model=list[LowStockResponse],
    dependencies=[
        Depends(require_permission("inventory:read"))
    ],
)
def low_stock_route(
    db: Session = Depends(get_db),
):
    try:
        return get_low_stock_items(db)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# =========================================================
# BULK UPLOAD
# Roles:
# warehouse_manager OR procurement_manager
# =========================================================

@router.post(
    "/bulk-upload",
    response_model=BulkUploadResponse,
)
def bulk_upload_route(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    auth=Depends(
        require_roles(
            "warehouse_manager",
            "procurement_manager",
        )
    ),
):
    start_time = time.perf_counter()

    try:
        result = bulk_upload_csv(
            db=db,
            file=file,
        )

        elapsed_seconds = (
            time.perf_counter() - start_time
        )

        return {
            **result,
            "elapsed_seconds": round(
                elapsed_seconds,
                4,
            ),
        }

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# =========================================================
# BULK UPDATE
# Roles:
# warehouse_manager OR procurement_manager
# =========================================================

@router.post(
    "/bulk-update",
)
def bulk_update_route(
    updates: list[BulkUpdateItem],
    db: Session = Depends(get_db),
    auth=Depends(
        require_roles(
            "warehouse_manager",
            "procurement_manager",
        )
    ),
):
    try:
        result = bulk_update_inventory(
            updates=updates,
            db=db,
        )

        return [
            inventory_response(
                inventory=item,
                db=db,
            )
            for item in result
        ]

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


# =========================================================
# WHAT-IF SIMULATION
# Roles:
# ceo OR vp_operations
# =========================================================

@router.post(
    "/what-if",
    response_model=WhatIfResponse,
)
async def what_if_route(
    request: WhatIfRequest,
    db: Session = Depends(get_db),
    auth=Depends(
        require_roles(
            "ceo",
            "vp_operations",
        )
    ),
):
    try:
        return what_if_simulation(
            db=db,
            spike_percent=request.spike_percent,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# =========================================================
# DEMAND GROWTH SIMULATION
# Permission: inventory:read
# =========================================================

@router.get(
    "/simulate",
    dependencies=[
        Depends(require_permission("inventory:read"))
    ],
)
def simulate_inventory(
    growth_percent: float = 30.0,
    db: Session = Depends(get_db),
):
    if growth_percent < 0:
        raise HTTPException(
            status_code=400,
            detail="Growth percentage cannot be negative",
        )

    try:
        return simulate_demand_growth(
            db=db,
            growth_percent=growth_percent,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# =========================================================
# DECREMENT INVENTORY
# Permission: inventory:write
#
# M3:
# Consume FIFO cost layers whenever stock leaves.
#
# Important:
# Missing cost layers must not block physical stock
# movement. They only affect valuation accuracy.
# =========================================================

@router.post(
    "/decrement",
    dependencies=[
        Depends(require_permission("inventory:write"))
    ],
)
def decrement_inventory_route(
    sku_id: str,
    warehouse_id: str,
    quantity: int,
    db: Session = Depends(get_db),
):
    if quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be greater than zero",
        )

    try:
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
            raise HTTPException(
                status_code=404,
                detail="Inventory not found",
            )

        if item.quantity_on_hand < quantity:
            raise HTTPException(
                status_code=409,
                detail="Insufficient stock",
            )

        # Consume FIFO cost layers before changing
        # the inventory quantity.
        consumed_layers = consume_cost_layers(
            db=db,
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            quantity=quantity,
        )

        consumed_quantity = sum(
            layer_quantity
            for layer_quantity, _unit_cost in consumed_layers
        )

        # Stock with no or partial cost history still moves.
        # Missing cost layers affect valuation accuracy;
        # they must not prevent the physical inventory movement.
        uncosted_quantity = quantity - consumed_quantity

        if uncosted_quantity > 0:
            logger.warning(
                "Decrement of %s units of %s at %s exceeded "
                "available cost layers by %s units; valuation "
                "for this SKU is incomplete until stock is "
                "received against a PO.",
                quantity,
                sku_id,
                warehouse_id,
                uncosted_quantity,
            )

        item.quantity_on_hand -= quantity

        db.commit()
        db.refresh(item)

        # -----------------------------------------------------
        # MILESTONE 2:
        # A sale is a common way stock falls below its
        # reorder point, so check whether an automatic
        # draft PO is required after the decrement.
        #
        # The decrement has already committed, so a missing
        # supplier configuration must not fail the movement.
        # -----------------------------------------------------
        try:
            generate_draft_po_if_required(
                db=db,
                inventory=item,
            )
        except ValueError:
            pass

        return inventory_response(
            inventory=item,
            db=db,
        )

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise


# =========================================================
# REORDER CHECK
# Permission: inventory:read
# =========================================================

@router.get(
    "/{sku_id}/{warehouse_id}/reorder-check",
    response_model=ReorderCheckResponse,
    dependencies=[
        Depends(require_permission("inventory:read"))
    ],
)
def reorder_check_route(
    sku_id: str,
    warehouse_id: str,
    db: Session = Depends(get_db),
):
    inventory = get_inventory(
        db=db,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
    )

    if inventory is None:
        raise HTTPException(
            status_code=404,
            detail="Inventory not found",
        )

    try:
        calculation = calculate_reorder_point(
            db=db,
            inventory=inventory,
        )

        reorder_point = calculation["reorder_point"]

        needs_reorder = (
            inventory.quantity_on_hand
            < reorder_point
        )

        suggested_order_qty = max(
            reorder_point - inventory.quantity_on_hand,
            0,
        )

        return {
            "sku_id": inventory.sku_id,
            "current_qty": inventory.quantity_on_hand,
            "reorder_point": reorder_point,
            "needs_reorder": needs_reorder,
            "suggested_order_qty": suggested_order_qty,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# =========================================================
# DEMAND SPIKE SIMULATION
# Permission: inventory:read
# =========================================================

@router.post(
    "/{sku_id}/{warehouse_id}/simulate",
    response_model=SimulationResponse,
    dependencies=[
        Depends(require_permission("inventory:read"))
    ],
)
def simulate_route(
    sku_id: str,
    warehouse_id: str,
    request: DemandSpikeRequest,
    db: Session = Depends(get_db),
):
    try:
        result = simulate_demand_spike(
            db=db,
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            demand_spike_percent=(
                request.demand_spike_percent
            ),
        )

        if result is None:
            raise HTTPException(
                status_code=404,
                detail="Inventory not found",
            )

        return result

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# =========================================================
# UPDATE INVENTORY
# Permission: inventory:write
# =========================================================

@router.put(
    "/{sku_id}/{warehouse_id}",
    response_model=InventoryResponse,
    dependencies=[
        Depends(require_permission("inventory:write"))
    ],
)
def update_inventory_route(
    sku_id: str,
    warehouse_id: str,
    inventory: InventoryUpdate,
    db: Session = Depends(get_db),
):
    try:
        result = update_inventory(
            db=db,
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            inventory=inventory,
        )

        if result is None:
            raise HTTPException(
                status_code=404,
                detail="Inventory not found",
            )

        return result

    except HTTPException:
        raise

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# =========================================================
# MULTI-ECHELON FULFILLMENT
# Permission: inventory:write
# =========================================================

@router.post(
    "/multi-echelon/fulfill",
    response_model=MultiEchelonResponse,
    dependencies=[
        Depends(require_permission("inventory:write"))
    ],
)
def multi_echelon_fulfill_route(
    sku_id: str,
    warehouse_id: str,
    required_quantity: int,
    db: Session = Depends(get_db),
):
    if required_quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Required quantity must be greater than zero",
        )

    try:
        return fulfill_shortage(
            db=db,
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            required_quantity=required_quantity,
        )

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# =========================================================
# GET SINGLE INVENTORY
# Permission: inventory:read
# =========================================================

@router.get(
    "/{sku_id}/{warehouse_id}",
    response_model=InventoryResponse,
    dependencies=[
        Depends(require_permission("inventory:read"))
    ],
)
def get_inventory_route(
    sku_id: str,
    warehouse_id: str,
    db: Session = Depends(get_db),
):
    item = get_inventory(
        db=db,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
    )

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Inventory not found",
        )

    try:
        return inventory_response(
            inventory=item,
            db=db,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# =========================================================
# DELETE INVENTORY
# Permission: inventory:write
# =========================================================

@router.delete(
    "/{sku_id}/{warehouse_id}",
    response_model=DeleteResponse,
    dependencies=[
        Depends(require_permission("inventory:write"))
    ],
)
def delete_inventory_route(
    sku_id: str,
    warehouse_id: str,
    db: Session = Depends(get_db),
):
    try:
        deleted = delete_inventory(
            db=db,
            sku_id=sku_id,
            warehouse_id=warehouse_id,
        )

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="Inventory not found",
            )

        return {
            "message": "Inventory deleted successfully"
        }

    except HTTPException:
        raise

    except Exception:
        db.rollback()
        raise
@router.get(
    "/network-optimization",
)
def network_optimization(
    days: int = 30,
    db: Session = Depends(get_db),
    auth=Depends(
        require_permission("inventory:read")
    ),
):
    try:
        return optimize_network_safety_stock(
            db=db,
            days=days,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc