from datetime import date, datetime
from enum import Enum
from typing import List

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# SHIPMENT STATUS
# ============================================================

class ShipmentStatus(str, Enum):
    created = "created"


# ============================================================
# SHIPMENT ITEM
# ============================================================

class ShipmentItem(BaseModel):
    item_code: str = Field(
        min_length=1,
        pattern=r"^[A-Za-z0-9_-]+$",
    )

    quantity: int = Field(
        gt=0,
    )


# ============================================================
# CREATE SHIPMENT NOTICE
# ============================================================

class ShipmentCreate(BaseModel):

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "po_number": "PO1001",
                "shipment_date": "2026-09-09",
                "expected_delivery_date": "2026-09-15",
                "carrier": "DHL",
                "tracking_number": "DHL123456789",
                "items": [
                    {
                        "item_code": "LAP001",
                        "quantity": 10,
                    },
                    {
                        "item_code": "MOU001",
                        "quantity": 10,
                    },
                ],
            }
        }
    )

    po_number: str = Field(
        pattern=r"^[A-Za-z0-9_-]+$"
    )

    shipment_date: date

    expected_delivery_date: date

    carrier: str = Field(
        min_length=1,
        max_length=100,
    )

    tracking_number: str = Field(
        min_length=1,
        max_length=100,
    )

    items: List[ShipmentItem] = Field(
        min_length=1,
    )


# ============================================================
# SHIPMENT RESPONSE
# ============================================================

class ShipmentResponse(BaseModel):

    shipment_id: str

    po_number: str

    supplier_id: str

    shipment_date: date

    expected_delivery_date: date

    carrier: str

    tracking_number: str

    items: List[ShipmentItem]

    status: ShipmentStatus

    created_at: datetime

    created_by: str