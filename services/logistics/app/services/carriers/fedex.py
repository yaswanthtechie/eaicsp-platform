import random

from app.services.carriers.base import (
    CarrierAdapter,
    CarrierError,
    api_retry,
)

from app.schemas.shipment import (
    Carrier,
    Status,
    CarrierRate,
    TrackingInfo,
)


class FedExAdapter(CarrierAdapter):

    @api_retry()
    def get_rate(
        self,
        origin: str,
        destination: str,
        weight_kg: float,
    ) -> CarrierRate:

        if random.random() < 0.3:
            raise CarrierError("FedEx API timeout")

        return CarrierRate(
            carrier=Carrier.fedex,
            origin=origin,
            destination=destination,
            weight_kg=weight_kg,
            price=950,
            estimated_days=3,
            reliability_score=0.92,
        )

    @api_retry()
    def get_tracking(
        self,
        tracking_number: str,
    ) -> TrackingInfo:

        return TrackingInfo(
            tracking_number=tracking_number,
            carrier=Carrier.fedex,
            status=Status.in_transit,
            location="In Transit",
            estimated_delivery=None,
        )