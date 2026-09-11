from datetime import date, datetime
from enum import Enum
from typing import List

from pydantic import BaseModel, ConfigDict, Field


class GoodsReceiptStatus(str, Enum):
    """
    Status of a Goods Receipt.

    A Goods Receipt is created only after the shipped
    Purchase Order goods are physically received.
    """

    received = "received"


class GoodsReceiptItem(BaseModel):
    """
    Represents one item received against a Purchase Order.
    """

    item_code: str = Field(
        min_length=1,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="Item code from the Purchase Order.",
    )

    quantity: int = Field(
        gt=0,
        description="Quantity physically received.",
    )


class GoodsReceiptCreate(BaseModel):
    """
    Request schema for creating a Goods Receipt.

    A Goods Receipt can be created only for a Purchase Order
    that has already reached the shipped P2P state.

    For the current Milestone 1 flow, the receipt represents
    the complete quantity ordered in the Purchase Order.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "po_number": "PO1001",
                "receipt_date": "2026-09-09",
                "warehouse": "WH-HYD-01",
                "received_by": "warehouse.user@company.com",
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
        min_length=1,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="Purchase Order number associated with this receipt.",
    )

    receipt_date: date = Field(
        description="Date on which the goods were physically received.",
    )

    warehouse: str = Field(
        min_length=1,
        max_length=100,
        description="Warehouse where the goods were received.",
    )

    received_by: str = Field(
        min_length=1,
        max_length=255,
        description="Person or user who recorded the goods receipt.",
    )

    items: List[GoodsReceiptItem] = Field(
        min_length=1,
        description="Items and quantities received against the Purchase Order.",
    )


class GoodsReceiptResponse(BaseModel):
    """
    Response schema returned after creating or retrieving
    a Goods Receipt.
    """

    receipt_id: str = Field(
        description="Unique identifier of the Goods Receipt.",
    )

    po_number: str = Field(
        description="Purchase Order associated with the Goods Receipt.",
    )

    supplier_id: str = Field(
        description="Supplier that owns the Purchase Order.",
    )

    receipt_date: date = Field(
        description="Date on which the goods were received.",
    )

    warehouse: str = Field(
        description="Warehouse where the goods were received.",
    )

    received_by: str = Field(
        description="Person or user who received the goods.",
    )

    items: List[GoodsReceiptItem] = Field(
        description="Items and quantities received.",
    )

    status: GoodsReceiptStatus = Field(
        description="Current status of the Goods Receipt.",
    )

    created_at: datetime = Field(
        description="Timestamp when the Goods Receipt record was created.",
    )

    created_by: str = Field(
        description="Authenticated user who created the Goods Receipt.",
    )

