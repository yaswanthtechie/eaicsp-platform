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
# BLUEDART CARRIER
# ============================================================

class BlueDartAdapter(BaseCarrier):
    """
    BlueDart carrier implementation.

    R4 features:
    - Uses BaseCarrier interface.
    - Uses Tenacity retry through api_retry().
    - Dynamic reliability is calculated by shipment_service.py.
    - Local circuit breaker is handled by shipment_service.py.
    """

    carrier = Carrier.bluedart

    base_price = 750.0

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
        Return BlueDart shipping rate.
        """

        # ----------------------------------------------------
        # VALIDATE WEIGHT
        # ----------------------------------------------------

        if weight_kg <= 0:

            raise CarrierError(
                "Invalid shipment weight"
            )

        # ----------------------------------------------------
        # RETURN RATE
        # ----------------------------------------------------

        return CarrierRate(
            carrier=self.carrier,
            origin=origin,
            destination=destination,
            weight_kg=weight_kg,
            price=self.base_price,
            estimated_days=self.estimated_days,

            # Default/mock value only.
            # shipment_service.py replaces this with
            # the dynamically calculated reliability score.
            reliability_score=0.90,
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
        Return BlueDart tracking information.
        """

        return TrackingInfo(
            tracking_number=tracking_number,
            carrier=self.carrier,
            status=Status.in_transit,
            location="In Transit",
            estimated_delivery=None,
        )