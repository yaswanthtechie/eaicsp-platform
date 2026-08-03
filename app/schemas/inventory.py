from typing import Optional
from pydantic import BaseModel, Field


class InventoryCreate(BaseModel):
    sku_id: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    warehouse_id: str = Field(min_length=1)
    quantity_on_hand: int = Field(ge=0)
    safety_stock: int = Field(ge=0)
    lead_time_days: int = Field(ge=0)
    avg_daily_demand: float = Field(gt=0)


class InventoryUpdate(BaseModel):
    product_name: Optional[str] = Field(default=None, min_length=1)
    quantity_on_hand: Optional[int] = Field(default=None, ge=0)
    safety_stock: Optional[int] = Field(default=None, ge=0)
    lead_time_days: Optional[int] = Field(default=None, ge=0)
    avg_daily_demand: Optional[float] = Field(default=None, gt=0)


class InventoryResponse(InventoryCreate):
    reorder_point: float


class BulkUpdateItem(BaseModel):
    sku_id: str = Field(min_length=1)
    warehouse_id: str = Field(min_length=1) 
    quantity_delta: int


class DemandSpikeRequest(BaseModel):
    spike_percent: float = Field(ge=0)


class LegacyDemandSpikeRequest(BaseModel):
    """Compatibility payload for the former per-SKU simulation endpoint."""
    demand_spike_percent: float = Field(ge=0)
