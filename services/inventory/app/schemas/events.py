from datetime import UTC, date, datetime
from typing import Annotated, Any, Literal, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    producer: str = "inventory-service"
    occurred_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    event_version: int = 1
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


class ComplianceSupplierStatusChangedPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    supplier_name: Optional[str] = None
    supplier_id: Optional[str] = None
    country: Optional[str] = None
    old_status: Optional[str] = None
    new_status: str
    matched_list: Optional[Any] = None
    reason: Optional[str] = None
    screening_run_id: Optional[str] = None


class ComplianceSupplierStatusChangedEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    event_id: str
    event_type: str = "compliance.supplier.status_changed"
    producer: str = "compliance-service"
    occurred_at: str
    event_version: int = 1
    payload: ComplianceSupplierStatusChangedPayload
    trace_id: Optional[str] = None


class DeadLetterEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    raw_message: str
    error: str
    failed_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    consumer_group: str = "inventory-service"
    topic: str
    partition: Optional[int] = None
    offset: Optional[int] = None


# ============================================================================
# Round 15: Contract-First Integration Event Schemas
# ============================================================================

class POApprovedLineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_number: int = Field(ge=1)
    sku_id: str = Field(pattern=r"^SKU-\d{6}$")
    quantity: int = Field(ge=1)
    unit_cost: float = Field(ge=0)
    expected_cost: float = Field(ge=0)


class POApprovedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    po_id: str = Field(pattern=r"^PO-\d{4}-\d{6}$")
    po_number: Optional[str] = None
    supplier_id: str = Field(pattern=r"^SUP-\d{5}$")
    warehouse_id: str = Field(pattern=r"^WH-[A-Z]{3}-\d{2}$")
    approval_status: Literal["approved"]
    approved_by: Annotated[str, Field(min_length=1)]
    approved_at: datetime
    total_amount: float = Field(ge=0)
    currency: str = "INR"
    expected_delivery_date: Optional[date] = None
    lines: list[POApprovedLineItem] = Field(min_length=1)


class InventoryPOApprovedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: uuid.UUID
    event_type: Literal["inventory.po.approved"] = "inventory.po.approved"
    event_version: Literal[1] = 1
    occurred_at: datetime
    producer: Literal["inventory-service"] = "inventory-service"
    trace_id: Optional[str] = None
    payload: POApprovedPayload


class POAcknowledgedPayload(BaseModel):
    """supplierportal.po.acknowledged v1 payload (contracts/events/supplierportal.po.acknowledged.v1.json)."""
    model_config = ConfigDict(extra="forbid")
    po_number: str = Field(pattern=r"^PO-\d{4}-\d{6}$")
    supplier_id: str = Field(pattern=r"^SUP-\d{5}$")
    acknowledged_at: datetime


class GoodsReceivedLineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku_id: str = Field(pattern=r"^SKU-\d{6}$")
    quantity_received: int = Field(ge=1)
    unit_cost: Optional[float] = Field(default=None, ge=0)


class GoodsReceivedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipt_id: str = Field(pattern=r"^GR-\d{4}-\d{6}$")
    po_id: str = Field(pattern=r"^PO-\d{4}-\d{6}$")
    po_number: Optional[str] = None
    supplier_id: str = Field(pattern=r"^SUP-\d{5}$")
    warehouse_id: str = Field(pattern=r"^WH-[A-Z]{3}-\d{2}$")
    received_by: str
    received_at: datetime
    status: Literal["received"] = "received"
    notes: Optional[str] = None
    items: list[GoodsReceivedLineItem] = Field(min_length=1)


class InventoryGoodsReceivedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: uuid.UUID
    event_type: Literal["inventory.goods.received"] = "inventory.goods.received"
    event_version: Literal[1] = 1
    occurred_at: datetime
    producer: Literal["inventory-service"] = "inventory-service"
    trace_id: Optional[str] = None
    payload: GoodsReceivedPayload
