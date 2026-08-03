from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.inventory import BulkUpdateItem, DemandSpikeRequest, InventoryCreate, InventoryResponse, InventoryUpdate, LegacyDemandSpikeRequest
from app.services.inventory_service import (InventoryOperationError, bulk_update_inventory, bulk_upload_csv,
    create_inventory, delete_inventory, get_all_inventory, get_inventory, get_inventory_locations, get_low_stock_items, get_reorder_plan,
    reorder_check, simulate_demand_spike, simulate_single_demand_spike, update_inventory)

router = APIRouter()


@router.post("", response_model=InventoryResponse, status_code=201)
def create_inventory_route(inventory: InventoryCreate, db: Session = Depends(get_db)):
    result = create_inventory(db, inventory)
    if result is None: raise HTTPException(409, "SKU already exists")
    return result


@router.get("", response_model=list[InventoryResponse])
def get_all_inventory_route(db: Session = Depends(get_db)):
    return get_all_inventory(db)


@router.get("/reorder-plan")
def reorder_plan_route(db: Session = Depends(get_db)):
    return {"plan": get_reorder_plan(db)}


@router.get("/low-stock")
def low_stock_route(db: Session = Depends(get_db)):
    return get_low_stock_items(db)


@router.post("/bulk-update", response_model=list[InventoryResponse])
def bulk_update_route(updates: list[BulkUpdateItem], db: Session = Depends(get_db)):
    try: return bulk_update_inventory(db, updates)
    except InventoryOperationError as exc: raise HTTPException(409, str(exc)) from exc


@router.post("/what-if")
def what_if_route(request: DemandSpikeRequest, db: Session = Depends(get_db)):
    return {"spike_percent": request.spike_percent, "affected_skus": simulate_demand_spike(db, request.spike_percent)}


@router.post("/bulk-upload")
def bulk_upload_csv_route(file: UploadFile = File(...), db: Session = Depends(get_db)):
    return bulk_upload_csv(db, file)


def _single_sku_item(db: Session, sku_id: str, warehouse_id: str | None = None):
    if warehouse_id is not None:
        item = get_inventory(db, sku_id, warehouse_id)
        if item is None:
            raise HTTPException(404, "Inventory not found")
        return item
    items = get_inventory_locations(db, sku_id)
    if not items:
        raise HTTPException(404, "Inventory not found")
    if len(items) > 1:
        raise HTTPException(409, "Specify warehouse_id: this SKU exists in multiple warehouses")
    return items[0]


# Legacy single-SKU API. It remains unambiguous only while the SKU has one
# warehouse record; new callers should use the warehouse-specific endpoints.
@router.get("/{sku_id}/reorder-check")
def legacy_reorder_check_route(sku_id: str, warehouse_id: str | None = None, db: Session = Depends(get_db)):
    item = _single_sku_item(db, sku_id, warehouse_id)
    return reorder_check(db, item.sku_id, item.warehouse_id)


@router.post("/{sku_id}/simulate")
def legacy_simulate_route(sku_id: str, request: LegacyDemandSpikeRequest, warehouse_id: str | None = None, db: Session = Depends(get_db)):
    return simulate_single_demand_spike(db, _single_sku_item(db, sku_id, warehouse_id), request.demand_spike_percent)


@router.get("/{sku_id}/{warehouse_id}/reorder-check")
def reorder_check_route(sku_id: str, warehouse_id: str, db: Session = Depends(get_db)):
    result = reorder_check(db, sku_id, warehouse_id)
    if result is None: raise HTTPException(404, "Inventory not found")
    return result


@router.get("/{sku_id}/{warehouse_id}", response_model=InventoryResponse)
def get_inventory_route(sku_id: str, warehouse_id: str, db: Session = Depends(get_db)):
    item = get_inventory(db, sku_id, warehouse_id)
    if item is None: raise HTTPException(404, "Inventory not found")
    from app.services.inventory_service import inventory_response
    return inventory_response(item)


@router.put("/{sku_id}/{warehouse_id}", response_model=InventoryResponse)
def update_inventory_route(sku_id: str, warehouse_id: str, inventory: InventoryUpdate, db: Session = Depends(get_db)):
    result = update_inventory(db, sku_id, warehouse_id, inventory)
    if result is None: raise HTTPException(404, "Inventory not found")
    return result


@router.delete("/{sku_id}/{warehouse_id}")
def delete_inventory_route(sku_id: str, warehouse_id: str, db: Session = Depends(get_db)):
    if not delete_inventory(db, sku_id, warehouse_id): raise HTTPException(404, "Inventory not found")
    return {"message": "Inventory deleted successfully"}


@router.get("/{sku_id}", response_model=InventoryResponse)
def legacy_get_inventory_route(sku_id: str, warehouse_id: str | None = None, db: Session = Depends(get_db)):
    from app.services.inventory_service import inventory_response
    return inventory_response(_single_sku_item(db, sku_id, warehouse_id))


@router.put("/{sku_id}", response_model=InventoryResponse)
def legacy_update_inventory_route(sku_id: str, inventory: InventoryUpdate, warehouse_id: str | None = None, db: Session = Depends(get_db)):
    item = _single_sku_item(db, sku_id, warehouse_id)
    return update_inventory(db, item.sku_id, item.warehouse_id, inventory)


@router.delete("/{sku_id}")
def legacy_delete_inventory_route(sku_id: str, warehouse_id: str | None = None, db: Session = Depends(get_db)):
    item = _single_sku_item(db, sku_id, warehouse_id)
    delete_inventory(db, item.sku_id, item.warehouse_id)
    return {"message": "Inventory deleted successfully"}
