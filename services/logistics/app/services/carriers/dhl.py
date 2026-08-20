from app.schemas.shipment import (
    Carrier,
    CarrierRate,
    Status,
    TrackingInfo,
)

from app.services.carriers.base import (
    BaseCarrier,
    CarrierError,
)


# ============================================================
# DHL CARRIER
# ============================================================

class DHLAdapter(BaseCarrier):
    """
    DHL carrier implementation.

    R4 features:
    - Uses the common BaseCarrier interface.
    - Retry is controlled by shipment_service.py.
    - Local circuit breaker is controlled by
      shipment_service.py.
    - Dynamic reliability is calculated from carrier history.
    """

    carrier = Carrier.dhl

    base_price = 850.0

    estimated_days = 2

    # --------------------------------------------------------
    # GET RATE
    # --------------------------------------------------------

    def get_rate(
        self,
        origin: str,
        destination: str,
        weight_kg: float,
    ) -> CarrierRate:
        """
        Return DHL shipping rate.

        Retry is intentionally NOT handled here.
        shipment_service.py controls retry + circuit breaker.
        """

        if weight_kg <= 0:
            raise CarrierError(
                "Invalid shipment weight"
            )

        return CarrierRate(
            carrier=self.carrier,
            origin=origin,
            destination=destination,
            weight_kg=weight_kg,
            price=self.base_price,
            estimated_days=self.estimated_days,

            # Default/mock value only.
            # shipment_service.py replaces this with the
            # dynamically calculated reliability score.
            reliability_score=0.87,
        )

    # --------------------------------------------------------
    # GET TRACKING
    # --------------------------------------------------------

    def get_tracking(
        self,
        tracking_number: str,
    ) -> TrackingInfo:
        """
        Return DHL tracking information.
        """

        return TrackingInfo(
            tracking_number=tracking_number,
            carrier=self.carrier,
            status=Status.in_transit,
            location="In Transit",
            estimated_delivery=None,
        )