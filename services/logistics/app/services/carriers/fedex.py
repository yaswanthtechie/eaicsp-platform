import random
import time

from app.services.carriers.base import (
    CarrierAdapter,
    CarrierError,
    CarrierRate,
    TrackingInfo,
)
from app.schemas.shipment import Carrier


class FedExAdapter(CarrierAdapter):
    """
    FedEx carrier adapter.

    Simulates:
    - Network latency
    - Temporary carrier failures
    - Shipping rate calculation
    - Tracking information
    """

    BASE_PRICE = 950.0
    ESTIMATED_DAYS = 3
    RELIABILITY_SCORE = 0.92

    # R4 requirement:
    # FedEx has a 30% temporary failure rate.
    FAILURE_RATE = 0.30

    def get_rate(
        self,
        origin: str,
        destination: str,
        weight_kg: float,
    ) -> CarrierRate:
        """
        Return FedEx shipping rate.

        A small delay simulates network/API latency.

        FedEx can simulate temporary API failures.

        Retry and circuit-breaker handling are controlled
        by shipment_service.py.
        """

        # ====================================================
        # VALIDATE WEIGHT
        # ====================================================

        if weight_kg <= 0:
            raise CarrierError(
                "Invalid shipment weight"
            )

        # ====================================================
        # SIMULATE NETWORK LATENCY
        # ====================================================

        time.sleep(
            random.uniform(
                0.05,
                0.15,
            )
        )

        # ====================================================
        # SIMULATE FEDEX FAILURE
        # ====================================================

        if (
            self.FAILURE_RATE > 0
            and random.random() < self.FAILURE_RATE
        ):
            raise CarrierError(
                "FedEx API timeout"
            )

        # ====================================================
        # CALCULATE PRICE
        # ====================================================

        price = (
            self.BASE_PRICE
            + (weight_kg * 10)
        )

        # ====================================================
        # RETURN RATE
        # ====================================================

        return CarrierRate(
            carrier=Carrier.fedex,
            origin=origin,
            destination=destination,
            weight_kg=weight_kg,
            price=round(
                price,
                2,
            ),
            estimated_days=self.ESTIMATED_DAYS,
            reliability_score=self.RELIABILITY_SCORE,
        )

    # ========================================================
    # TRACKING
    # ========================================================

    def get_tracking(
        self,
        tracking_id: str,
    ) -> TrackingInfo:
        """
        Return FedEx tracking information.
        """

        if (
            not tracking_id
            or not str(tracking_id).strip()
        ):
            raise CarrierError(
                "Tracking ID is required"
            )

        return TrackingInfo(
            carrier=Carrier.fedex,
            tracking_number=str(
                tracking_id
            ),
            status="in_transit",
            location="FedEx Hub",
            estimated_delivery=None,
        )