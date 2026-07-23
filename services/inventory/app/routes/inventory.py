from fastapi import APIRouter, Depends, HTTPException,File,UploadFile
import csv
from io import StringIO
from sqlalchemy.orm import Session
from app.models.inventory import Inventory



from app.database import get_db
from app.schemas.inventory import (
    InventoryCreate,
    InventoryUpdate,
    InventoryResponse,
    DemandSpikeRequest,
)

from app.services.inventory_service import (
    create_inventory,
    get_all_inventory,
    get_inventory,
    update_inventory,
    delete_inventory,
    reorder_check,
    get_low_stock_items,
    simulate_demand_spike,
    bulk_upload_csv
)

router = APIRouter()



@router.post("/", response_model=InventoryResponse, status_code=201)
def create_inventory_route(
    item: InventoryCreate,
    db: Session = Depends(get_db),
):
    return create_inventory(db, item)



@router.get("/", response_model=list[InventoryResponse])
def get_all_inventory_route(
    db: Session = Depends(get_db),
):
    return get_all_inventory(db)


@router.get("/low-stock", response_model=list[dict])
def low_stock_route(
    db: Session = Depends(get_db),
):
    return get_low_stock_items(db)


@router.get("/{sku_id}", response_model=InventoryResponse)
def get_inventory_route(
    sku_id: str,
    db: Session = Depends(get_db),
):
    inventory = get_inventory(db, sku_id)

    if inventory is None:
        raise HTTPException(
            status_code=404,
            detail="Inventory not found"
        )

    return inventory


@router.put("/{sku_id}", response_model=InventoryResponse)
def update_inventory_route(
    sku_id: str,
    item: InventoryUpdate,
    db: Session = Depends(get_db),
):
    inventory = update_inventory(
        db,
        sku_id,
        item,
    )

    if inventory is None:
        raise HTTPException(
            status_code=404,
            detail="Inventory not found"
        )

    return inventory


@router.delete("/{sku_id}")
def delete_inventory_route(
    sku_id: str,
    db: Session = Depends(get_db),
):
    deleted = delete_inventory(
        db,
        sku_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Inventory not found"
        )

    return {
        "message": "Inventory deleted successfully"
    }


@router.get("/v1/inventory/{sku_id}/reorder-check")
def reorder_check_route(
    sku_id: str,
    db: Session = Depends(get_db),
):
    result = reorder_check(
        db,
        sku_id,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Inventory not found"
        )

    return result


@router.post("/v1/inventory/{sku_id}/simulate")
def simulate_demand_route(
    sku_id: str,
    request: DemandSpikeRequest,
    db: Session = Depends(get_db),
):
    result = simulate_demand_spike(
        db,
        sku_id,
        request.demand_spike_percent,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Inventory not found"
        )

    return result

@router.post("/inventory/bulk-upload")
def bulk_upload_csv_route(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    return bulk_upload_csv(db, file)
