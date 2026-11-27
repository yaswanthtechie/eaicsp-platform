from datetime import datetime
from typing import Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class InventoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku_id: str
    product_name: str
    warehouse_id: str
    category: str = "Uncategorized"

    quantity_on_hand: int = Field(ge=0)

    lead_time_days: int = Field(ge=0)

    safety_stock: int = Field(ge=0)

    # M1
    warehouse_type: Literal[
        "central",
        "regional",
        "local",
    ] = "local"

    parent_warehouse_id: Optional[str] = None
    unit_cost: Optional[float] = Field(
        default=None,
        ge=0,
    )


class InventoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_name: Optional[str] = None

    category: Optional[str] = None

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

    # M1
    warehouse_type: Optional[
        Literal[
            "central",
            "regional",
            "local",
        ]
    ] = None

    parent_warehouse_id: Optional[str] = None
    version: int


class InventoryResponse(BaseModel):
    sku_id: str
    product_name: str
    warehouse_id: str
    category: str
    quantity_on_hand: int
    reorder_point: int
    avg_daily_demand: float
    lead_time_days: int
    safety_stock: int

    # M1
    warehouse_type: str
    parent_warehouse_id: Optional[str] = None
    version: int


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
    demand_spike_percent: float = Field(ge=0)


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

    transfer_suggestion: Optional[TransferSuggestion] = None


class WhatIfRequest(BaseModel):
    spike_percent: float = Field(ge=0)


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


class MultiEchelonResponse(BaseModel):
    status: str
    sku_id: str
    warehouse_id: str
    required_quantity: int
    transferred_quantity: int
    supplier_quantity: int
    transfers: list[dict]
    supplier_po: Optional[dict] = None


class TransferRecommendationNumbers(BaseModel):
    model_config = ConfigDict(extra="ignore")

    destination_quantity_on_hand: int
    destination_reorder_point: int
    shortage_quantity: int
    recommended_quantity: int
    po_lead_time_days: int
    po_unit_cost: float
    po_cost: float
    source_warehouse_id: Optional[str] = None
    source_quantity_on_hand: Optional[int] = None
    source_reorder_point: Optional[int] = None
    source_stock_cover_days: Optional[float] = None
    source_excess_quantity: Optional[int] = None
    transfer_lead_time_days: Optional[int] = None
    transfer_cost_per_unit: Optional[float] = None
    transfer_cost: Optional[float] = None
    cost_share_ratio: Optional[float] = None
    max_allowed_cost_share: float
    min_stock_cover_days: float


class TransferRecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sku_id: str
    product_name: str
    destination_warehouse_id: str
    recommendation: str
    reason: str
    source_warehouse_id: Optional[str] = None
    recommended_quantity: int
    days_saved: int = 0
    estimated_cost_savings: float = 0.0
    numbers: TransferRecommendationNumbers


class SafetyStockInputs(BaseModel):
    model_config = ConfigDict(extra="ignore")

    avg_daily_demand: float
    sd_daily_demand: float
    demand_cv: float
    demand_history_days: int
    demand_window_weeks: int
    avg_lead_time_days: float
    sd_lead_time_days: float
    lead_time_po_count: int
    lead_time_source: str
    supplier_id: Optional[str] = None


class SafetyStockResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sku_id: str
    warehouse_id: str
    abc_class: str
    xyz_class: str
    abc_xyz_class: str
    service_level: float
    z_score: float
    inputs_used: SafetyStockInputs
    calculated_safety_stock: float
    safety_stock: int
    current_safety_stock: int
    method: str
    is_fallback: bool
    fallback_reason: Optional[str] = None


class ReservationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku_id: str = Field(min_length=1)
    warehouse_id: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    ttl_seconds: Optional[int] = Field(default=None, gt=0)


class ReservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reservation_id: str
    sku_id: str
    warehouse_id: str
    quantity: int
    status: str
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
