from pydantic import BaseModel
from typing import Optional


class InventoryCreate(BaseModel):
    sku_id: str
    product_name: str
    warehouse_id: str
    quantity_on_hand: int
    safety_stock: int
    lead_time_days: int
    avg_daily_demand: float


class InventoryUpdate(BaseModel):
    product_name: Optional[str] = None
    warehouse_id: Optional[str] = None
    quantity_on_hand: Optional[int] = None
    safety_stock: Optional[int] = None
    lead_time_days: Optional[int] = None
    avg_daily_demand: Optional[float] = None


class InventoryResponse(BaseModel):
    sku_id: str
    product_name: str
    warehouse_id: str
    quantity_on_hand: int
    reorder_point: int
    safety_stock: int
    lead_time_days: int
    avg_daily_demand: float

    model_config = {
        "from_attributes": True
    }


class DemandSpikeRequest(BaseModel):
    demand_spike_percent: float


class ReorderCheckResponse(BaseModel):
    sku_id: str
    current_qty: int
    reorder_point: int
    needs_reorder: bool
    suggested_order_qty: int


class LowStockResponse(BaseModel):
    sku_id: str
    product_name: str
    quantity_on_hand: int
    reorder_point: int


class SimulationResponse(BaseModel):
    sku_id: str
    current_quantity: int
    new_reorder_point: int
    needs_reorder: bool
    suggested_order_qty: int


class DeleteResponse(BaseModel):
    message: str


class BulkUploadResponse(BaseModel):
    message: str
    total_records: int