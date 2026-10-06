from datetime import UTC, datetime
from typing import Any, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    producer: str = "inventory-service"
    occurred_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    event_version: str = "1.0"
    payload: dict[str, Any]
    trace_id: Optional[str] = None


class StockLowPayload(BaseModel):
    sku_id: str
    warehouse_id: str
    quantity_on_hand: int
    reorder_point: int
    safety_stock: int
    urgency_days: Optional[int] = None


class PurchaseOrderDraftedPayload(BaseModel):
    po_id: str
    sku_id: str
    warehouse_id: str
    supplier_id: str
    quantity: int
    unit_cost: float
    expected_cost: float
    status: str = "draft"
    created_at: str
