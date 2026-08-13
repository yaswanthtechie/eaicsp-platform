from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================
# SHIPMENT STATUS
# ============================================================

class Status(str, Enum):
    pending = "pending"
    in_transit = "in_transit"
    delivered = "delivered"
    delayed = "delayed"
    cancelled = "cancelled"


# ============================================================
# CARRIER
# ============================================================

class Carrier(str, Enum):
    dhl = "dhl"
    fedex = "fedex"
    ups = "ups"
    bluedart = "bluedart"


# ============================================================
# SHIPMENT CREATE
# ============================================================

class ShipmentCreate(BaseModel):
    shipment_id: int
    origin: str
    destination: str
    carrier: Carrier
    status: Status
    estimated_delivery: date
    actual_delivery: Optional[date] = None
    weight_kg: float = Field(gt=0)

    @field_validator("carrier", mode="before")
    @classmethod
    def normalize_carrier(cls, value):

        if isinstance(value, str):
            return value.lower()

        return value


# ============================================================
# QUOTE PREFERENCE
# ============================================================

class QuotePreference(str, Enum):
    cheapest = "cheapest"
    fastest = "fastest"
    most_reliable = "most_reliable"


# ============================================================
# SINGLE QUOTE REQUEST
# ============================================================

class QuoteRequest(BaseModel):
    origin: str
    destination: str
    weight_kg: float = Field(gt=0)

    preference: QuotePreference = (
        QuotePreference.cheapest
    )


# ============================================================
# CARRIER RATE
# ============================================================

class CarrierRate(BaseModel):
    carrier: Carrier
    origin: str
    destination: str
    weight_kg: float
    price: float
    estimated_days: int
    reliability_score: float = Field(
        ge=0,
        le=1,
    )


# ============================================================
# QUOTE RESPONSE
# ============================================================

class QuoteResponse(BaseModel):
    rates: list[CarrierRate]
    warnings: list[str] = Field(
        default_factory=list
    )


# ============================================================
# BULK QUOTE REQUEST
# ============================================================

class BulkQuoteRequest(BaseModel):
    shipments: list[QuoteRequest] = Field(
        min_length=1,
        max_length=20,
    )


# ============================================================
# BULK PERFORMANCE
# ============================================================

class BulkQuotePerformance(BaseModel):
    shipment_count: int
    sequential_seconds: float
    parallel_seconds: float
    speedup: float


# ============================================================
# BULK QUOTE RESPONSE
# ============================================================

class BulkQuoteResponse(BaseModel):
    quotes: list[QuoteResponse]
    performance: BulkQuotePerformance


# ============================================================
# SHIPMENT EVENT
# ============================================================

class ShipmentEvent(BaseModel):
    shipment_id: int
    status: Status
    timestamp: datetime
    location: str


# ============================================================
# TRACKING
# ============================================================

class TrackingInfo(BaseModel):
    tracking_number: str
    carrier: Carrier
    status: Status
    location: str
    estimated_delivery: Optional[str] = None