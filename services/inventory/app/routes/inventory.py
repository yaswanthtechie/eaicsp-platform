from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
)

from sqlalchemy.orm import Session

from app.models.inventory import Inventory

from app.database import get_db

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
)

from app.services.reorder_service import (
    calculate_reorder_point,
    calculate_urgency_score,
)

from app.services.transfer_service import (
    find_transfer_suggestion,
)
from app.services.simulation_service import (
    simulate_demand_growth,
)


router = APIRouter()


# =========================================================
# CREATE
# =========================================================

@router.post(
    "",
    response_model=InventoryResponse,
    status_code=201,
)
def create_inventory_route(
    inventory: InventoryCreate,
    db: Session = Depends(get_db),
):

    try:

        result = create_inventory(
            db,
            inventory,
        )

        if result is None:

            raise HTTPException(
                status_code=409,
                detail=(
                    "SKU already exists "
                    "in warehouse"
                ),
            )

        return inventory_response(
            result,
            db,
        )

    except HTTPException:
        
        raise

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# =========================================================
# GET ALL
# =========================================================

@router.get(
    "",
    response_model=list[
        InventoryResponse
    ],
)
def get_all_inventory_route(
    db: Session = Depends(get_db),
):

    try:

        items = get_all_inventory(db)

        return [
            inventory_response(
                item,
                db,
            )
            for item in items
        ]

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# =========================================================
# REORDER PLAN
# IMPORTANT: static route before dynamic routes
# =========================================================

@router.get(
    "/reorder-plan",
    response_model=list[
        ReorderPlanEntry
    ],
)
def reorder_plan(
    db: Session = Depends(get_db),
):

    inventories = (
        db.query(Inventory)
        .all()
    )

    result = []

    for inventory in inventories:

        try:

            calculation = (
                calculate_reorder_point(
                    db=db,
                    inventory=inventory,
                )
            )

            reorder_point = (
                calculation[
                    "reorder_point"
                ]
            )

            # Only items below ROP.
            if (
                inventory.quantity_on_hand
                >= reorder_point
            ):
                continue

            avg_demand = (
                calculation[
                    "rolling_avg_demand"
                ]
            )

            urgency_score = (
                calculate_urgency_score(
                    quantity_on_hand=(
                        inventory.quantity_on_hand
                    ),

                    reorder_point=(
                        reorder_point
                    ),

                    avg_daily_demand=(
                        avg_demand
                    ),
                )
            )

            transfer = (
                find_transfer_suggestion(
                    db=db,
                    destination=inventory,
                    destination_reorder_point=(
                        reorder_point
                    ),
                )
            )

            result.append(
                {
                    "sku_id": (
                        inventory.sku_id
                    ),

                    "product_name": (
                        inventory.product_name
                    ),

                    "warehouse_id": (
                        inventory.warehouse_id
                    ),

                    "quantity_on_hand": (
                        inventory.quantity_on_hand
                    ),

                    "reorder_point": (
                        reorder_point
                    ),

                    "urgency_score": (
                        urgency_score
                    ),

                    "rolling_avg_demand": (
                        avg_demand
                    ),

                    "abc_tier": (
                        calculation[
                            "abc_tier"
                        ]
                    ),

                    "adjusted_safety_stock": (
                        calculation[
                            "adjusted_safety_stock"
                        ]
                    ),

                    "transfer_suggestion": (
                        transfer
                    ),
                }
            )

        except ValueError as exc:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid inventory data "
                    f"for {inventory.sku_id}/"
                    f"{inventory.warehouse_id}: "
                    f"{exc}"
                ),
            )

    result.sort(
        key=lambda item: (
            item["urgency_score"]
        ),
        reverse=True,
    )

    return result


# =========================================================
# LOW STOCK
# =========================================================

@router.get(
    "/low-stock",
    response_model=list[
        LowStockResponse
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
# BULK CSV
# =========================================================

@router.post(
    "/bulk-upload",
    response_model=BulkUploadResponse,
)
def bulk_upload_route(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):

    try:

        return bulk_upload_csv(
            db,
            file,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# =========================================================
# BULK UPDATE
# =========================================================

@router.post(
    "/bulk-update",
    response_model=list[
        InventoryResponse
    ],
)
def bulk_update_route(
    updates: list[
        BulkUpdateItem
    ],
    db: Session = Depends(get_db),
):

    try:

        result = bulk_update_inventory(
            updates,
            db,
        )

        return [
            inventory_response(
                item,
                db,
            )
            for item in result
        ]

    except ValueError as exc:

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )


# =========================================================
# WHAT IF
# =========================================================

@router.post(
    "/what-if",
    response_model=WhatIfResponse,
)
def what_if_route(
    request: WhatIfRequest,
    db: Session = Depends(get_db),
):

    try:

        return what_if_simulation(
            db,
            request.spike_percent,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# =========================================================
# DECREMENT
# =========================================================

@router.post(
    "/decrement",
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
            detail=(
                "Quantity must be "
                "greater than zero"
            ),
        )

    # PostgreSQL SELECT FOR UPDATE
    item = (
        db.query(Inventory)
        .filter(
            Inventory.sku_id == sku_id,

            Inventory.warehouse_id
            == warehouse_id,
        )
        .with_for_update()
        .first()
    )

    if item is None:

        raise HTTPException(
            status_code=404,
            detail="Inventory not found",
        )

    if (
        item.quantity_on_hand
        < quantity
    ):

        raise HTTPException(
            status_code=409,
            detail="Insufficient stock",
        )

    item.quantity_on_hand -= quantity

    db.commit()

    db.refresh(item)

    return inventory_response(
        item,
        db,
    )


# =========================================================
# GET SINGLE
# =========================================================

@router.get(
    "/{sku_id}/{warehouse_id}",
    response_model=InventoryResponse,
)
def get_inventory_route(
    sku_id: str,
    warehouse_id: str,
    db: Session = Depends(get_db),
):

    item = get_inventory(
        db,
        sku_id,
        warehouse_id,
    )

    if item is None:

        raise HTTPException(
            status_code=404,
            detail="Inventory not found",
        )

    try:

        return inventory_response(
            item,
            db,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# =========================================================
# UPDATE
# =========================================================

@router.put(
    "/{sku_id}/{warehouse_id}",
    response_model=InventoryResponse,
)
def update_inventory_route(
    sku_id: str,
    warehouse_id: str,
    inventory: InventoryUpdate,
    db: Session = Depends(get_db),
):

    try:

        result = update_inventory(
            db,
            sku_id,
            warehouse_id,
            inventory,
        )

        if result is None:

            raise HTTPException(
                status_code=404,
                detail="Inventory not found",
            )

        return inventory_response(
            result,
            db,
        )

    except HTTPException:

        raise

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# =========================================================
# DELETE
# =========================================================

@router.delete(
    "/{sku_id}/{warehouse_id}",
    response_model=DeleteResponse,
)
def delete_inventory_route(
    sku_id: str,
    warehouse_id: str,
    db: Session = Depends(get_db),
):

    deleted = delete_inventory(
        db,
        sku_id,
        warehouse_id,
    )

    if not deleted:

        raise HTTPException(
            status_code=404,
            detail="Inventory not found",
        )

    return {
        "message": (
            "Inventory deleted successfully"
        )
    }


# =========================================================
# REORDER CHECK
# =========================================================

@router.get(
    "/{sku_id}/{warehouse_id}/reorder-check",
    response_model=ReorderCheckResponse,
)
def reorder_check_route(
    sku_id: str,
    warehouse_id: str,
    db: Session = Depends(get_db),
):

    inventory = (
        db.query(Inventory)
        .filter(
            Inventory.sku_id == sku_id,

            Inventory.warehouse_id
            == warehouse_id,
        )
        .first()
    )

    if inventory is None:

        raise HTTPException(
            status_code=404,
            detail="Inventory not found",
        )

    try:

        calculation = (
            calculate_reorder_point(
                db=db,
                inventory=inventory,
            )
        )

        reorder_point = (
            calculation[
                "reorder_point"
            ]
        )

        needs_reorder = (
            inventory.quantity_on_hand
            < reorder_point
        )

        suggested_order_qty = max(
            reorder_point
            - inventory.quantity_on_hand,
            0,
        )

        return {
            "sku_id": (
                inventory.sku_id
            ),

            "current_qty": (
                inventory.quantity_on_hand
            ),

            "reorder_point": (
                reorder_point
            ),

            "needs_reorder": (
                needs_reorder
            ),

            "suggested_order_qty": (
                suggested_order_qty
            ),
        }

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# =========================================================
# SIMULATE ONE SKU
# =========================================================

@router.post(
    "/{sku_id}/{warehouse_id}/simulate",
    response_model=SimulationResponse,
)
def simulate_route(
    sku_id: str,
    warehouse_id: str,
    request: DemandSpikeRequest,
    db: Session = Depends(get_db),
):

    try:

        result = (
            simulate_demand_spike(
                db,
                sku_id,
                warehouse_id,
                request.demand_spike_percent,
            )
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

@router.get("/simulate")
def simulate_inventory(
    growth_percent: float = 30.0,
    db: Session = Depends(get_db),
):
    if growth_percent < 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Growth percentage "
                "cannot be negative"
            ),
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