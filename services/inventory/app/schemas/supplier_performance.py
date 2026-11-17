"""Supplier performance schema (R15 / #325)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SupplierPerformanceResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    supplier_id: str
    supplier_name: Optional[str] = None
    received_po_count: int = Field(ge=0)
    on_time_po_count: int = Field(ge=0)
    on_time_delivery_percent: float | None = Field(default=None, ge=0.0, le=100.0)
    total_po_count: int = Field(default=0, ge=0)
    open_po_count: int = Field(default=0, ge=0)
    cancelled_po_count: int = Field(default=0, ge=0)
    late_po_count: int = Field(default=0, ge=0)
    unverified_po_count: int = Field(default=0, ge=0)
