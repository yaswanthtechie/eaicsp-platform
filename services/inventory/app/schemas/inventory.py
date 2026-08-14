from pydantic import BaseModel
from typing import Optional



# Create Inventory

class InventoryCreate(BaseModel):
    sku_id: str
    product_name: str
    warehouse_id: str
    quantity_on_hand: int
    avg_daily_demand: float
    lead_time_days: int
    safety_stock: int



class InventoryUpdate(BaseModel):
    product_name: Optional[str] = None
    warehouse_id: Optional[str] = None
    quantity_on_hand: Optional[int] = None
    avg_daily_demand: Optional[float] = None
    lead_time_days: Optional[int] = None
    safety_stock: Optional[int] = None



class InventoryResponse(BaseModel):
    sku_id: str
    product_name: str
    warehouse_id: str
    quantity_on_hand: int
    reorder_point: int
    avg_daily_demand: float
    lead_time_days: int
    safety_stock: int

    model_config = {
        "from_attributes": True
    }


# -------------------------
# Reorder Check
# -------------------------
class ReorderCheckResponse(BaseModel):
    sku_id: str
    current_qty: int
    reorder_point: int
    needs_reorder: bool
    suggested_order_qty: int


# -------------------------
# Low Stock
# -------------------------
class LowStockResponse(BaseModel):
    sku_id: str
    product_name: str
    quantity_on_hand: int
    reorder_point: int


# -------------------------
# Demand Spike
# -------------------------
class DemandSpikeRequest(BaseModel):
    demand_spike_percent: float


class SimulationResponse(BaseModel):
    sku_id: str
    current_quantity: int
    new_reorder_point: int
    needs_reorder: bool
    suggested_order_qty: int


# -------------------------
# Bulk Update
# -------------------------
class BulkUpdateItem(BaseModel):
    sku_id: str
    warehouse_id: str
    quantity_delta: int


# -------------------------
# Reorder Plan
# -------------------------
class ReorderPlanEntry(BaseModel):
    sku_id: str
    product_name: str
    warehouse_id: str
    quantity_on_hand: int
    reorder_point: int
    urgency_score: float


# -------------------------
# What If
# -------------------------
class WhatIfRequest(BaseModel):
    spike_percent: float


# -------------------------
# Delete Response
# -------------------------
class DeleteResponse(BaseModel):
    message: str


# -------------------------
# CSV Upload
# -------------------------
class BulkUploadResponse(BaseModel):
    message: str
    total_records: int