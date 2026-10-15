from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class GoodsReceiptItemCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sku_id: str = Field(description="Canonical Product / SKU ID (e.g. SKU-000123)")
    quantity_received: int = Field(gt=0, description="Quantity physically received into warehouse")
    unit_cost: Optional[float] = Field(default=None, ge=0, description="Unit cost at receipt")


class GoodsReceiptCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    po_id: str = Field(description="Associated canonical Purchase Order ID (e.g. PO-2026-000123)")
    warehouse_id: str = Field(description="Canonical Destination Warehouse ID (e.g. WH-BLR-01)")
    received_by: str = Field(description="Username or email of warehouse receiving manager")
    items: List[GoodsReceiptItemCreate] = Field(min_length=1, description="List of received SKU items")
    notes: Optional[str] = Field(default=None, description="Optional delivery or inspection notes")


class GoodsReceiptItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sku_id: str = Field(description="Canonical Product / SKU ID (e.g. SKU-000123)")
    quantity_received: int = Field(gt=0, description="Quantity physically received")
    unit_cost: Optional[float] = Field(default=None, ge=0, description="Unit cost")


class GoodsReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    receipt_id: str = Field(description="Canonical Goods Receipt ID (e.g. GR-2026-000077)")
    po_id: str = Field(description="Associated Purchase Order ID")
    supplier_id: str = Field(description="Canonical Supplier ID (e.g. SUP-00045)")
    warehouse_id: str = Field(description="Destination Warehouse ID (e.g. WH-BLR-01)")
    received_by: str = Field(description="User that processed the receipt")
    received_at: datetime = Field(description="Timestamp of receipt")
    status: str = Field(default="received", description="Status of the goods receipt")
    items: List[GoodsReceiptItemResponse] = Field(description="Received line items")
    notes: Optional[str] = Field(default=None, description="Receiver notes")
