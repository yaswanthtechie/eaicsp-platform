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
    """
    Data required to create or update a shipment.
    """

    shipment_id: int = Field(
        gt=0,
        description="Shipment ID must be greater than 0.",
    )

    origin: str = Field(
        min_length=1,
        max_length=100,
        description="Shipment origin.",
    )

    destination: str = Field(
        min_length=1,
        max_length=100,
        description="Shipment destination.",
    )

    carrier: Carrier

    status: Status

    estimated_delivery: date

    actual_delivery: Optional[date] = None

    weight_kg: float = Field(
        gt=0,
        le=50_000,
        description="Shipment weight in kilograms.",
    )

    # --------------------------------------------------------
    # NORMALIZE CARRIER
    # --------------------------------------------------------

    @field_validator(
        "carrier",
        mode="before",
    )
    @classmethod
    def normalize_carrier(cls, value):

        if isinstance(value, str):
            return value.strip().lower()

        return value

    # --------------------------------------------------------
    # NORMALIZE ORIGIN
    # --------------------------------------------------------

    @field_validator(
        "origin",
        mode="before",
    )
    @classmethod
    def normalize_origin(cls, value):

        if isinstance(value, str):
            return value.strip()

        return value

    # --------------------------------------------------------
    # NORMALIZE DESTINATION
    # --------------------------------------------------------

    @field_validator(
        "destination",
        mode="before",
    )
    @classmethod
    def normalize_destination(cls, value):

        if isinstance(value, str):
            return value.strip()

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
    """
    Request used to calculate a shipment quote.
    """

    origin: str = Field(
        min_length=1,
        max_length=100,
        description="Shipment origin.",
    )

    destination: str = Field(
        min_length=1,
        max_length=100,
        description="Shipment destination.",
    )

    weight_kg: float = Field(
        gt=0,
        le=50_000,
        description="Shipment weight in kilograms.",
    )

    preference: QuotePreference = (
        QuotePreference.cheapest
    )

    # --------------------------------------------------------
    # NORMALIZE ORIGIN
    # --------------------------------------------------------

    @field_validator(
        "origin",
        mode="before",
    )
    @classmethod
    def normalize_origin(cls, value):

        if isinstance(value, str):
            return value.strip()

        return value

    # --------------------------------------------------------
    # NORMALIZE DESTINATION
    # --------------------------------------------------------

    @field_validator(
        "destination",
        mode="before",
    )
    @classmethod
    def normalize_destination(cls, value):

        if isinstance(value, str):
            return value.strip()

        return value


# ============================================================
# CARRIER RATE
# ============================================================

class CarrierRate(BaseModel):
    """
    Rate returned by a carrier.

    reliability_score is dynamically replaced by
    shipment_service.py using carrier history.
    """

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
    """
    Quote response for one shipment.
    """

    rates: list[CarrierRate]

    warnings: list[str] = Field(
        default_factory=list
    )


# ============================================================
# BULK QUOTE REQUEST - R4
# ============================================================

class BulkQuoteRequest(BaseModel):
    """
    Request for multiple shipment quotes.

    R4 requirement:

        Minimum = 1 shipment
        Maximum = 20 shipments
    """

    shipments: list[QuoteRequest] = Field(
        min_length=1,
        max_length=20,
        description=(
            "1 to 20 shipment quote requests."
        ),
    )


# ============================================================
# BULK QUOTE PERFORMANCE - R4
# ============================================================

class BulkQuotePerformance(BaseModel):
    """
    Performance information for R4 bulk quoting.

    Normal request:

        shipment_count
        parallel_seconds

    Benchmark request:

        shipment_count
        parallel_seconds
        sequential_seconds
        speedup
    """

    shipment_count: int = Field(
        ge=1,
        le=20,
    )

    parallel_seconds: float = Field(
        ge=0,
    )

    sequential_seconds: Optional[float] = Field(
        default=None,
        ge=0,
    )

    speedup: Optional[float] = Field(
        default=None,
        ge=0,
    )


# ============================================================
# BULK QUOTE RESPONSE - R4
# ============================================================

class BulkQuoteResponse(BaseModel):
    """
    Response for the R4 bulk quote endpoint.
    """

    quotes: list[QuoteResponse]

    performance: BulkQuotePerformance


# ============================================================
# SHIPMENT EVENT
# ============================================================

class ShipmentEvent(BaseModel):
    """
    Shipment status history event.
    """

    shipment_id: int

    status: Status

    timestamp: datetime

    location: str


# ============================================================
# TRACKING
# ============================================================

class TrackingInfo(BaseModel):
    """
    Carrier tracking information.
    """

    tracking_number: str

    carrier: Carrier

    status: Status

    location: str

    estimated_delivery: Optional[str] = None