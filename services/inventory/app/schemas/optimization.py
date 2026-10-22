from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class RecommendationLineItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sku_id: str = Field(description="Canonical Product / SKU ID (e.g. SKU-000123)")
    warehouse_id: str = Field(description="Canonical Warehouse ID (e.g. WH-BLR-01)")
    supplier_id: str = Field(description="Canonical Supplier ID (e.g. SUP-00045)")
    current_stock: int = Field(ge=0, description="Current on-hand inventory")
    reorder_point: int = Field(ge=0, description="Calculated reorder point threshold")
    safety_stock: int = Field(ge=0, description="Target safety stock level")
    forecast_demand: float = Field(ge=0, description="Projected demand over horizon")
    forecast_source: Literal["model", "fallback"] = Field(
        description="'model' if served by Forecast Service; 'fallback' if 28-day moving average"
    )
    recommended_order_quantity: int = Field(gt=0, description="Computed replenishment order quantity")
    estimated_unit_cost: float = Field(ge=0, description="Supplier unit cost")
    estimated_total_cost: float = Field(ge=0, description="Total expected replenishment cost")


class OptimizationRecommendationsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    generated_at: datetime = Field(description="UTC timestamp of recommendation generation")
    recommendations: List[RecommendationLineItem] = Field(description="List of recommended purchase orders")
    total_recommended_spend: float = Field(ge=0, description="Sum of estimated costs across recommendations")
