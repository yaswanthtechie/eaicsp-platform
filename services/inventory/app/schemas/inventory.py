from pydantic import BaseModel
from typing import Optional


class InventoryItem(BaseModel):
    sku_id: str
    product_name: str
    warehouse_id: str
    quantity_on_hand: int
    reorder_point: Optional[int] = None
    safety_stock: int
    lead_time_days: int
    avg_daily_demand: int

    model_config = {
        "from_attributes": True
    }


class InventoryCreate(BaseModel):
    sku_id: str
    product_name: str
    warehouse_id: str
    quantity_on_hand: int
    safety_stock: int
    lead_time_days: int
    avg_daily_demand: int


class InventoryUpdate(BaseModel):
    product_name: Optional[str] = None
    warehouse_id: Optional[str] = None
    quantity_on_hand: Optional[int] = None
    safety_stock: Optional[int] = None
    lead_time_days: Optional[int] = None
    avg_daily_demand: Optional[int] = None


class InventoryResponse(BaseModel):
    sku_id: str
    product_name: str
    warehouse_id: str
    quantity_on_hand: int
    reorder_point: Optional[int] = None
    safety_stock: int
    lead_time_days: int
    avg_daily_demand: int

    model_config = {
        "from_attributes": True
    }


class DemandSpikeRequest(BaseModel):
    demand_spike_percent: float