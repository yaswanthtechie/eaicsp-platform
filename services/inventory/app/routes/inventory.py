from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
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
)

from app.services.inventory_service import (
    create_inventory,
    get_all_inventory,
    get_inventory,
    update_inventory,
    delete_inventory,
    reorder_check,
    get_low_stock_items,
    get_reorder_plan,
    simulate_demand_spike,
    bulk_upload_csv,
    bulk_update_inventory,
    what_if_simulation,
    inventory_response,
)


router = APIRouter()


# ---------------------------------------
# CREATE INVENTORY
# ---------------------------------------

@router.post(
    "",
    response_model=InventoryResponse,
    status_code=201,
)
def create_inventory_route(
    inventory: InventoryCreate,
    db: Session = Depends(get_db),
):

    result = create_inventory(
        db,
        inventory
    )

    if result is None:
        raise HTTPException(
            status_code=409,
            detail="SKU already exists in warehouse",
        )

    return result



# ---------------------------------------
# GET ALL INVENTORY
# ---------------------------------------

@router.get(
    "",
    response_model=list[InventoryResponse],
)
def get_all_inventory_route(
    db: Session = Depends(get_db),
):

    return get_all_inventory(db)



# ---------------------------------------
# GET SKU FROM WAREHOUSE
# ---------------------------------------

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
        warehouse_id
    )

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Inventory not found",
        )

    return inventory_response(item)



# ---------------------------------------
# UPDATE WAREHOUSE INVENTORY
# ---------------------------------------

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

    return result



# ---------------------------------------
# DELETE WAREHOUSE INVENTORY
# ---------------------------------------

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
        "message": "Inventory deleted successfully"
    }



# ---------------------------------------
# REORDER CHECK
# ---------------------------------------

@router.get(
    "/{sku_id}/{warehouse_id}/reorder-check",
    response_model=ReorderCheckResponse,
)
def reorder_check_route(
    sku_id: str,
    warehouse_id: str,
    db: Session = Depends(get_db),
): 

    result = reorder_check(
        db,
        sku_id,
        warehouse_id,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Inventory not found",
        )

    return result



# ---------------------------------------
# REORDER PLAN ALL WAREHOUSES
# ---------------------------------------

@router.get(
    "/reorder-plan",
    response_model=list[ReorderPlanEntry],
)
def reorder_plan_route(
    db: Session = Depends(get_db),
):

    return get_reorder_plan(db)



# ---------------------------------------
# LOW STOCK
# ---------------------------------------

@router.get(
    "/low-stock",
    response_model=list[LowStockResponse],
)
def low_stock_route(
    db: Session = Depends(get_db),
):

    return get_low_stock_items(db)



# ---------------------------------------
# DEMAND SPIKE SIMULATION
# ---------------------------------------

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

    result = simulate_demand_spike(
        db,
        sku_id,
        warehouse_id,
        request.demand_spike_percent,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Inventory not found",
        )

    return result



# ---------------------------------------
# BULK CSV UPLOAD
# ---------------------------------------

@router.post(
    "/bulk-upload",
    response_model=BulkUploadResponse,
)
def bulk_upload_route(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):

    return bulk_upload_csv(
        db,
        file
    )



# ---------------------------------------
# BULK UPDATE TRANSACTION
# ---------------------------------------

@router.post(
    "/bulk-update",
    response_model=list[InventoryResponse],
)
def bulk_update_route(
    updates: list[BulkUpdateItem],
    db: Session = Depends(get_db),
):

    try:
        return bulk_update_inventory(
            updates,
            db
        )

    except Exception as exc:

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )



# ---------------------------------------
# WHAT IF DEMAND SPIKE
# ---------------------------------------

@router.post(
    "/what-if",
)
def what_if_route(
    request: WhatIfRequest,
    db: Session = Depends(get_db),
):

    return what_if_simulation(
        db,
        request.spike_percent,
    )
@router.post("/decrement")
def decrement_inventory_route(
    sku_id: str,
    warehouse_id: str,
    quantity: int,
    db: Session = Depends(get_db),
):

    item = (
        db.query(Inventory)
        .filter(
            Inventory.sku_id == sku_id,
            Inventory.warehouse_id == warehouse_id
        )
        .with_for_update()
        .first()
    )


    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Inventory not found"
        )


    if item.quantity_on_hand < quantity:
        raise HTTPException(
            status_code=409,
            detail="Insufficient stock"
        )


    item.quantity_on_hand -= quantity


    db.commit()

    db.refresh(item)


    return inventory_response(item)