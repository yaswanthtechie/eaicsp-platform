from pydantic import BaseModel, Field, field_validator
from enum import Enum
from datetime import date, datetime
from typing import Optional


class Status(str, Enum):
    pending = "pending"
    in_transit = "in_transit"
    delivered = "delivered"
    delayed = "delayed"
    cancelled = "cancelled"


class Carrier(str, Enum):
    dhl = "dhl"
    fedex = "fedex"
    ups = "ups"
    bluedart = "bluedart"


class ShipmentCreate(BaseModel):
    shipment_id: int
    origin: str
    destination: str
    carrier: Carrier
    status: Status
    estimated_delivery: date
    actual_delivery: Optional[date] = None
    weight_kg: float

    @field_validator("carrier", mode="before")
    @classmethod
    def normalize_carrier(cls, value):
        if isinstance(value, str):
            return value.lower()
        return value


class QuotePreference(str, Enum):
    cheapest = "cheapest"
    fastest = "fastest"
    most_reliable = "most_reliable"


class QuoteRequest(BaseModel):
    origin: str
    destination: str
    weight_kg: float
    preference: QuotePreference = QuotePreference.cheapest


class CarrierRate(BaseModel):
    carrier: Carrier
    origin: str
    destination: str
    weight_kg: float
    price: float
    estimated_days: int
    reliability_score: float


class QuoteResponse(BaseModel):
    rates: list[CarrierRate]
    warnings: list[str] = Field(default_factory=list)


class BulkQuoteRequest(BaseModel):
    shipments: list[QuoteRequest]

    @field_validator("shipments")
    @classmethod
    def check_max_shipments(cls, value):
        if len(value) > 20:
            raise ValueError("Batch quote supports up to 20 shipments")
        return value


class BulkQuoteResponse(BaseModel):
    quotes: list[QuoteResponse]


class ShipmentEvent(BaseModel):
    shipment_id: int
    status: Status
    timestamp: datetime
    location: str


class TrackingInfo(BaseModel):
    tracking_number: str
    carrier: Carrier
    status: Status
    location: str
    estimated_delivery: Optional[str] = None