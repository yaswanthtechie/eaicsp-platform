from enum import Enum
from typing import List

from pydantic import BaseModel, Field
from datetime import datetime, date


class PurchaseOrderStatus(str, Enum):
    draft = "draft"
    sent = "sent"
    acknowledged = "acknowledged"
    fulfilled = "fulfilled"
    cancelled = "cancelled"

class PurchaseOrderHistory(BaseModel):
    from_status: PurchaseOrderStatus
    to_status: PurchaseOrderStatus
    timestamp: datetime


class PurchaseOrderCreate(BaseModel):
    po_number: str = Field(..., example="PO1001")
    supplier_id: str = Field(..., example="SUP001")
    items: List[str]
    total_amount: float
    created_at: datetime
    expected_delivery: date


class PurchaseOrderUpdate(BaseModel):
    supplier_id: str | None = None
    items: List[str] | None = None
    total_amount: float | None = None
    expected_delivery: date | None = None


class PurchaseOrderResponse(BaseModel):
    po_number: str
    supplier_id: str
    items: List[str]
    total_amount: float
    status: PurchaseOrderStatus
    created_at: datetime
    expected_delivery: date
    history: List[PurchaseOrderHistory] = []

#responce when po deleted successfully
class MessageResponse(BaseModel):
    message: str


class PurchaseOrderTransition(BaseModel):
    target_state : PurchaseOrderStatus


