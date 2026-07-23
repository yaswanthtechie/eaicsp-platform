from pydantic import BaseModel
from enum import Enum
from datetime import date
from typing import Optional


class Status(str, Enum):
    pending = "pending"
    in_transit = "in_transit"
    delivered = "delivered"
    delayed = "delayed"
    cancelled = "cancelled"
 

class ShipmentCreate(BaseModel):
    shipment_id: int
    origin: str
    destination: str
    carrier: str
    status: Status
    estimated_delivery: date
    actual_delivery: Optional[date] = None
    weight_kg: float