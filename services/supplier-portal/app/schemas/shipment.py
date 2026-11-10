from datetime import date, datetime
from enum import Enum
from typing import List

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ============================================================
# SHIPMENT STATUS
# ============================================================

class ShipmentStatus(str, Enum):
    created = "created"


# ============================================================
# SHIPMENT ITEM
# ============================================================

class ShipmentItem(BaseModel):
    """
    One shipped line. Legacy POs use item_code;
    Inventory POs (po_mirror) use the canonical sku_id.
    """

    item_code: str | None = Field(
        default=None,
        min_length=1,
        pattern=r"^[A-Za-z0-9_-]+$",
    )

    sku_id: str | None = Field(
        default=None,
        pattern=r"^SKU-\d{6}$",
    )

    quantity: int = Field(
        gt=0,
    )

    @model_validator(mode="after")
    def validate_item_identifier(self):
        if not self.item_code and not self.sku_id:
            raise ValueError(
                "Either item_code or sku_id must be provided."
            )
        return self

# ============================================================
# CREATE SHIPMENT NOTICE
# ============================================================

class ShipmentCreate(BaseModel):

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "po_number": "PO-2026-000123",
                "shipment_date": "2026-09-09",
                "expected_delivery_date": "2026-09-15",
                "carrier": "DHL",
                "tracking_number": "DHL123456789",
                "origin": "Supplier Warehouse, Bengaluru",
                "destination_warehouse": "WH-BLR-01",
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

    origin: str = Field(
        min_length=1,
        max_length=255,
    )

    destination_warehouse: str = Field(
        pattern=r"^WH-[A-Z]{3}-[0-9]{2}$"
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

    origin: str

    destination_warehouse: str

    items: List[ShipmentItem]

    status: ShipmentStatus

    created_at: datetime

    created_by: str

    dispatched_at: datetime | None = None

    eta_days: float | None = None

    confidence_low: float | None = None

    confidence_high: float | None = None

    model_version: str | None = None

    predicted_at: datetime | None = None
