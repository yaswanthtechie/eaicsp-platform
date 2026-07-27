from pydantic import BaseModel, field_validator
from enum import Enum
from datetime import date
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


class QuoteRequest(BaseModel):
    origin: str
    destination: str
    weight_kg: float


class CarrierRate(BaseModel):
    carrier: Carrier
    origin: str
    destination: str
    weight_kg: float
    price: float
    estimated_days: int


class TrackingInfo(BaseModel):
    tracking_number: str
    carrier: Carrier
    status: Status
    location: str
    estimated_delivery: Optional[str] = None