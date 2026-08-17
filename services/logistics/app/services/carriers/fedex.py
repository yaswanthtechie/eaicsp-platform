import random

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
# FEDEX CARRIER
# ============================================================

class FedExAdapter(BaseCarrier):
    """
    FedEx carrier implementation.

    R4 features:
    - Carrier API failure simulation.
    - Tenacity retry through api_retry().
    - Local circuit breaker is handled by shipment_service.py.
    - Dynamic reliability is calculated from carrier history.
    """

    carrier = Carrier.fedex

    base_price = 950.0

    estimated_days = 3

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
        Return FedEx shipping rate.

        Approximately 30% of requests simulate
        a FedEx API timeout.
        """

        # ----------------------------------------------------
        # VALIDATE WEIGHT
        # ----------------------------------------------------

        if weight_kg <= 0:

            raise CarrierError(
                "Invalid shipment weight"
            )

        # ----------------------------------------------------
        # SIMULATE FEDEX FAILURE
        # ----------------------------------------------------

        if random.random() < 0.30:

            raise CarrierError(
                "FedEx API timeout"
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
            reliability_score=0.92,
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
        Return FedEx tracking information.
        """

        return TrackingInfo(
            tracking_number=tracking_number,
            carrier=self.carrier,
            status=Status.in_transit,
            location="In Transit",
            estimated_delivery=None,
        )