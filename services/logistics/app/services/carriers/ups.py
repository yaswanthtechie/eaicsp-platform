from app.services.carriers.base import CarrierAdapter, api_retry
from app.schemas.shipment import (
    Carrier,
    Status,
    CarrierRate,
    TrackingInfo
)


class UPSAdapter(CarrierAdapter):

    @api_retry()
    def get_rate(
        self,
        origin: str,
        destination: str,
        weight_kg: float
    ) -> CarrierRate:

        return CarrierRate(
            carrier=Carrier.ups,
            origin=origin,
            destination=destination,
            weight_kg=weight_kg,
            price=900,
            estimated_days=4,
            reliability_score=0.95,
        )

    @api_retry()
    def get_tracking(
        self,
        tracking_number: str
    ) -> TrackingInfo:

        return TrackingInfo(
            tracking_number=tracking_number,
            carrier=Carrier.ups,
            status=Status.in_transit,
            location="In Transit",
            estimated_delivery=None
        )