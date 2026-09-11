from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ============================================================
# THREE-WAY MATCH STATUS
# ============================================================

class ThreeWayMatchStatus(str, Enum):
    matched = "matched"
    discrepancy = "discrepancy"


# ============================================================
# DISCREPANCY TYPES
# ============================================================

class DiscrepancyType(str, Enum):
    quantity_mismatch = "quantity_mismatch"
    price_mismatch = "price_mismatch"


# ============================================================
# MATCH LINE RESULT
# ============================================================

class ThreeWayMatchLine(BaseModel):
    po_number: str
    item_code: str

    po_quantity: float
    received_quantity: float
    invoiced_quantity: float

    po_unit_price: float
    invoice_unit_price: float

    price_difference_percentage: float

    quantity_matched: bool
    price_matched: bool

    discrepancies: list[DiscrepancyType] = Field(
        default_factory=list
    )


# ============================================================
# THREE-WAY MATCH RESPONSE
# ============================================================

class ThreeWayMatchResponse(BaseModel):
    match_id: str

    supplier_id: str
    invoice_number: str

    status: ThreeWayMatchStatus

    lines: list[ThreeWayMatchLine]

    discrepancies: list[DiscrepancyType] = Field(
        default_factory=list
    )

    created_at: datetime
    created_by: str


# ============================================================
# DISCREPANCY RESOLUTION REQUEST
# ============================================================

class ThreeWayMatchResolution(BaseModel):
    reason: str = Field(
        ...,
        min_length=3,
        max_length=1000,
    )


# ============================================================
# PAYMENT APPROVAL RESPONSE
# ============================================================

class PaymentApprovalResponse(BaseModel):
    supplier_id: str
    invoice_number: str

    payment_status: str

    approved_at: datetime
    approved_by: str
    approved_role: str