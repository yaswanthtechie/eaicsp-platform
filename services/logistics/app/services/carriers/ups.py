import random
import time

from app.services.carriers.base import (
    CarrierAdapter,
    CarrierError,
    CarrierRate,
    TrackingInfo,
)
from app.schemas.shipment import Carrier


class UPSAdapter(CarrierAdapter):
    """
    UPS carrier adapter.

    Simulates network latency and provides
    shipping quotes and tracking information.
    """

    BASE_PRICE = 900.0
    ESTIMATED_DAYS = 4
    RELIABILITY_SCORE = 0.95

    def get_rate(
        self,
        origin: str,
        destination: str,
        weight_kg: float,
    ) -> CarrierRate:
        """
        Return UPS shipping rate.

        A small delay simulates an external carrier API.
        """

        if weight_kg <= 0:
            raise CarrierError("Invalid shipment weight")

        # Simulate network/API latency.
        time.sleep(random.uniform(0.05, 0.15))

        price = self.BASE_PRICE + (weight_kg * 10)

        return CarrierRate(
            carrier=Carrier.ups,
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
        """
        Return UPS tracking information.
        """

        if not tracking_id or not str(tracking_id).strip():
            raise CarrierError("Tracking ID is required")

        return TrackingInfo(
            carrier=Carrier.ups,
            tracking_number=str(tracking_id),
            status="in_transit",
            location="UPS Hub",
            estimated_delivery=None,
        )