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
    po_number: str
    supplier_id: str
    actor: str | None = None
    from_status: PurchaseOrderStatus
    to_status: PurchaseOrderStatus
    timestamp: datetime

class PurchaseOrderItem(BaseModel):
    item_code: str
    description: str
    quantity: int = Field(gt=0)
    unit_price: float = Field(gt=0)

class PurchaseOrderCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "po_number": "PO1001",
                "supplier_id": "SUP001",
                "items": [
                    {
                        "item_code": "LAP001",
                        "description": "Laptop",
                        "quantity": 10,
                        "unit_price": 50000
                    },
                    {
                        "item_code": "MOU001",
                        "description": "Wireless Mouse",
                        "quantity": 10,
                        "unit_price": 1500
                    }
                ],
                "total_amount": 515000,
                "created_at": "2026-08-06T10:00:00",
                "expected_delivery": "2026-08-30"
            }
        }
    )

    po_number: str = Field(
        pattern=r"^[A-Za-z0-9_-]+$"
    )

    supplier_id: str = Field(
        pattern=r"^[A-Za-z0-9_-]+$"
    )

    items: List[PurchaseOrderItem] = Field(
        min_length=1
    )

    total_amount: float = Field(
        gt=0
    )
    created_at: datetime
    expected_delivery: date


class PurchaseOrderUpdate(BaseModel):
    supplier_id: str | None = None
    items: List[PurchaseOrderItem] | None = None
    total_amount: float | None = None
    expected_delivery: date | None = None


class PurchaseOrderResponse(BaseModel):
    po_number: str
    supplier_id: str
    items: List[PurchaseOrderItem]
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


# ============================================================
# BULK SEND PURCHASE ORDERS
# ============================================================

class BulkPOSendRequest(BaseModel):
    """
    Request body for sending multiple Purchase Orders at once.
    """

    po_numbers: List[str] = Field(
        min_length=1
    )
    
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "po_numbers": [
                    "PO1001",
                    "PO1002",
                    "PO1003",
                    "PO9999"
                ]
            }
        }
    )


class BulkPOSendResult(BaseModel):
    """
    Result for one Purchase Order in a bulk-send operation.
    """

    po_number: str
    success: bool
    status: PurchaseOrderStatus | None = None
    error: str | None = None


class BulkPOSendResponse(BaseModel):
    """
    Overall response for the bulk-send operation.
    """

    total: int
    successful: int
    failed: int
    results: List[BulkPOSendResult]

