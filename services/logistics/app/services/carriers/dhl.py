import random
import time

from app.services.carriers.base import (
    BaseCarrier,
    CarrierError,
)
from app.schemas.shipment import (
    Carrier,
    CarrierRate,
    TrackingInfo,
)


class DHLAdapter(BaseCarrier):

    BASE_PRICE = 850.0
    ESTIMATED_DAYS = 2
    RELIABILITY_SCORE = 0.87

    def get_rate(
        self,
        origin: str,
        destination: str,
        weight_kg: float,
    ) -> CarrierRate:

        if weight_kg <= 0:
            raise CarrierError("Invalid shipment weight")

        # Simulate carrier/network latency
        time.sleep(random.uniform(0.05, 0.15))

        price = self.BASE_PRICE + (weight_kg * 10)

        return CarrierRate(
            carrier=Carrier.dhl,
            origin=origin,
            destination=destination,
            weight_kg=weight_kg,
            price=round(price, 2),
            estimated_days=self.ESTIMATED_DAYS,
            reliability_score=self.RELIABILITY_SCORE,
        )

    def get_tracking(
        self,
        tracking_id: str,
    ) -> TrackingInfo:

        if not tracking_id or not str(tracking_id).strip():
            raise CarrierError("Tracking ID is required")

        return TrackingInfo(
            carrier=Carrier.dhl,
            tracking_number=str(tracking_id),
            status="in_transit",
            location="DHL Hub",
            estimated_delivery=None,
        )