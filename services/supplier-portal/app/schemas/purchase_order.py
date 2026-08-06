from enum import Enum
from typing import List

from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, date


class PurchaseOrderStatus(str, Enum):
    draft = "draft"
    sent = "sent"
    acknowledged = "acknowledged"
    fulfilled = "fulfilled"
    cancelled = "cancelled"

class PurchaseOrderHistory(BaseModel):
    actor: str
    from_status: PurchaseOrderStatus
    to_status: PurchaseOrderStatus
    timestamp: datetime


class PurchaseOrderCreate(BaseModel):

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "po_number": "PO1001",
                "supplier_id": "SUP001",
                "items": [
                    "Laptop",
                    "Mouse"
                ],
                "total_amount": 50000,
                "created_at": "2026-08-06T10:00:00",
                "expected_delivery": "2026-08-30"
            }
        }
    )

    po_number: str
    supplier_id: str
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
    actual_delivery_date: date | None = None
    history: List[PurchaseOrderHistory] = Field(default_factory=list)

#responce when po deleted successfully
class MessageResponse(BaseModel):
    message: str


class PurchaseOrderTransition(BaseModel):
    target_state : PurchaseOrderStatus
    actor: str


