from app.schemas.shipment import (
    Carrier,
    CarrierRate,
    TrackingInfo,
)

from app.services.carriers.base import (
    BaseCarrier,
    CarrierError,
)


class FedExAdapter(BaseCarrier):
    """
    FedEx carrier adapter.

    Provides:
    - Shipping rate calculation
    - Tracking information

    Retry and circuit-breaker handling are performed
    by shipment_service.py.
    """

    BASE_PRICE = 950.0
    ESTIMATED_DAYS = 3
    RELIABILITY_SCORE = 0.92

    # ========================================================
    # GET RATE
    # ========================================================

    def get_rate(
        self,
        origin: str,
        destination: str,
        weight_kg: float,
    ) -> CarrierRate:
        """
        Return FedEx shipping rate.

        The method is deterministic so the carrier unit
        tests do not randomly fail.
        """

        # ----------------------------------------------------
        # VALIDATE WEIGHT
        # ----------------------------------------------------

        if weight_kg <= 0:
            raise CarrierError(
                "Invalid shipment weight"
            )

        # ----------------------------------------------------
        # VALIDATE ORIGIN
        # ----------------------------------------------------

        if not origin or not origin.strip():
            raise CarrierError(
                "Origin is required"
            )

        # ----------------------------------------------------
        # VALIDATE DESTINATION
        # ----------------------------------------------------

        if not destination or not destination.strip():
            raise CarrierError(
                "Destination is required"
            )

        # ----------------------------------------------------
        # CALCULATE PRICE
        # ----------------------------------------------------

        price = (
            self.BASE_PRICE
            + (weight_kg * 10)
        )

        # ----------------------------------------------------
        # RETURN RATE
        # ----------------------------------------------------

        return CarrierRate(
            carrier=Carrier.fedex,
            origin=origin,
            destination=destination,
            weight_kg=weight_kg,
            price=round(price, 2),
            estimated_days=self.ESTIMATED_DAYS,
            reliability_score=self.RELIABILITY_SCORE,
        )

    # ========================================================
    # GET TRACKING
    # ========================================================

    def get_tracking(
        self,
        tracking_id: str,
    ) -> TrackingInfo:
        """
        Return FedEx tracking information.
        """

        if not tracking_id or not str(tracking_id).strip():
            raise CarrierError(
                "Tracking ID is required"
            )

        return TrackingInfo(
            carrier=Carrier.fedex,
            tracking_number=str(tracking_id),
            status="in_transit",
            location="FedEx Hub",
            estimated_delivery=None,
        )