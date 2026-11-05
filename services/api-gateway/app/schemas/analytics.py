"""Pydantic schemas for contracts/openapi/analytics-kpis.yaml (contract_version v1)."""

from typing import Literal

from pydantic import BaseModel, Field

RateStatus = Literal["on_target", "warning", "critical", "no_data"]


class FiltersApplied(BaseModel):
    warehouse_id: str | None = None
    category: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    window_days: int = Field(default=30, ge=1, le=365)


class FillRateKpi(BaseModel):
    current_rate: float | None = Field(default=None, ge=0.0, le=100.0)
    target_rate: float = Field(default=95.0, ge=0.0, le=100.0)
    total_lines_ordered: int = Field(ge=0)
    lines_fulfilled: int = Field(ge=0)
    status: RateStatus
    trend: Literal["up", "down", "stable"]
    change_percentage: float | None = None


class WarehouseStockout(BaseModel):
    warehouse_id: str = Field(pattern=r"^WH-[A-Z]{3}-\d{2}$")
    stockout_count: int = Field(ge=0)
    at_risk_count: int | None = None
    total_skus: int = Field(ge=0)


class StockoutsKpi(BaseModel):
    total_stockouts: int = Field(ge=0)
    critical_skus: int | None = None
    at_risk_skus: int | None = None
    status: Literal["normal", "warning", "critical"]
    trend: Literal["improving", "worsening", "stable"]
    by_warehouse: list[WarehouseStockout] = Field(default_factory=list)


class POByStatus(BaseModel):
    draft: int | None = None
    approved: int = Field(ge=0)
    acknowledged: int = Field(ge=0)
    in_transit: int = Field(ge=0)


class OpenPurchaseOrdersKpi(BaseModel):
    total_open_orders: int = Field(ge=0)
    total_value_usd: float | None = None
    pending_approval: int | None = None
    by_status: POByStatus


class OnTimeDeliveryKpi(BaseModel):
    current_rate: float | None = Field(default=None, ge=0.0, le=100.0)
    target_rate: float = Field(default=95.0, ge=0.0, le=100.0)
    total_shipments: int = Field(ge=0)
    delivered_on_time: int = Field(ge=0)
    delayed: int = Field(ge=0)
    status: RateStatus
    trend: Literal["up", "down", "stable"]
    change_percentage: float | None = None


class KpisPayload(BaseModel):
    fill_rate: FillRateKpi
    stockouts: StockoutsKpi
    open_purchase_orders: OpenPurchaseOrdersKpi
    on_time_delivery: OnTimeDeliveryKpi


class KpiDashboardResponse(BaseModel):
    contract_version: Literal["v1"] = "v1"
    generated_at: str
    cached: bool
    cache_ttl_seconds: int | None = None
    filters_applied: FiltersApplied
    kpis: KpisPayload
