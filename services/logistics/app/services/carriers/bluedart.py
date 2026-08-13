import time

from app.services.carriers.base import (
    CarrierAdapter,
    api_retry,
)

from app.schemas.shipment import (
    Carrier,
    Status,
    CarrierRate,
    TrackingInfo,
)


class BlueDartAdapter(CarrierAdapter):

    @api_retry()
    def get_rate(
        self,
        origin: str,
        destination: str,
        weight_kg: float,
    ) -> CarrierRate:

        time.sleep(0.10)

        return CarrierRate(
            carrier=Carrier.bluedart,
            origin=origin,
            destination=destination,
            weight_kg=weight_kg,
            price=750,
            estimated_days=2,
            reliability_score=0.90,
        )

    @api_retry()
    def get_tracking(
        self,
        tracking_number: str,
    ) -> TrackingInfo:

        time.sleep(0.05)

        return TrackingInfo(
            tracking_number=tracking_number,
            carrier=Carrier.bluedart,
            status=Status.in_transit,
            location="In Transit",
            estimated_delivery=None,
        )