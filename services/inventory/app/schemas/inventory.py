from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class InventoryCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    sku_id: str
    product_name: str
    warehouse_id: str

    quantity_on_hand: int = Field(
        ge=0
    )

    lead_time_days: int = Field(
        ge=0
    )

    safety_stock: int = Field(
        ge=0
    )


class InventoryUpdate(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    product_name: Optional[str] = None

    quantity_on_hand: Optional[int] = Field(
        default=None,
        ge=0,
    )

    lead_time_days: Optional[int] = Field(
        default=None,
        ge=0,
    )

    safety_stock: Optional[int] = Field(
        default=None,
        ge=0,
    )


class InventoryResponse(BaseModel):
    sku_id: str
    product_name: str
    warehouse_id: str
    quantity_on_hand: int
    reorder_point: int
    avg_daily_demand: float
    lead_time_days: int
    safety_stock: int


class ReorderCheckResponse(BaseModel):
    sku_id: str
    current_qty: int
    reorder_point: int
    needs_reorder: bool
    suggested_order_qty: int


class LowStockResponse(BaseModel):
    sku_id: str
    product_name: str
    warehouse_id: str
    quantity_on_hand: int
    reorder_point: int
    urgency_days: int


class DemandSpikeRequest(BaseModel):
    demand_spike_percent: float = Field(
        ge=0
    )


class SimulationResponse(BaseModel):
    sku_id: str
    current_quantity: int
    new_reorder_point: int
    needs_reorder: bool
    suggested_order_qty: int


class BulkUpdateItem(BaseModel):
    sku_id: str
    warehouse_id: str
    quantity_delta: int


class TransferSuggestion(BaseModel):
    sku_id: str
    source_warehouse: str
    destination_warehouse: str
    transfer_quantity: int
    source_excess_quantity: int
    destination_shortage_quantity: int
    recommendation: str
    days_saved_vs_reorder: int


class ReorderPlanEntry(BaseModel):
    sku_id: str
    product_name: str
    warehouse_id: str
    quantity_on_hand: int
    reorder_point: int
    urgency_score: float
    rolling_avg_demand: float
    abc_tier: str
    adjusted_safety_stock: int

    transfer_suggestion: Optional[
        TransferSuggestion
    ] = None


class WhatIfRequest(BaseModel):
    spike_percent: float = Field(
        ge=0
    )


class WhatIfItem(BaseModel):
    sku_id: str
    current_quantity: int
    new_reorder_point: int
    needs_reorder: bool
    suggested_order_qty: int


class WhatIfResponse(BaseModel):
    spike_percent: float
    total_items: int
    affected_items: int
    total_suggested_order_qty: int
    details: list[WhatIfItem]


class DeleteResponse(BaseModel):
    message: str


class BulkUploadResponse(BaseModel):
    message: str
    total_records: int
    