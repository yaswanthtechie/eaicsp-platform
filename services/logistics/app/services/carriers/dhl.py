from app.schemas.shipment import (
    Carrier,
    CarrierRate,
    Status,
    TrackingInfo,
)

from app.services.carriers.base import (
    BaseCarrier,
    CarrierError,
    api_retry,
)


# ============================================================
# DHL CARRIER
# ============================================================

class DHLAdapter(BaseCarrier):
    """
    DHL carrier implementation.

    R4:
    - Uses the common BaseCarrier interface.
    - Uses Tenacity retry through api_retry().
    - Dynamic reliability is calculated by shipment_service.py.
    """

    carrier = Carrier.dhl

    base_price = 850.0

    estimated_days = 2

    # --------------------------------------------------------
    # GET RATE
    # --------------------------------------------------------

    @api_retry()
    def get_rate(
        self,
        origin: str,
        destination: str,
        weight_kg: float,
    ) -> CarrierRate:
        """
        Return DHL shipping rate.
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

            # This is only the carrier's default/mock value.
            # shipment_service.py replaces it with the
            # dynamically calculated history-based score.
            reliability_score=0.87,
        )

    # --------------------------------------------------------
    # GET TRACKING
    # --------------------------------------------------------

    @api_retry()
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