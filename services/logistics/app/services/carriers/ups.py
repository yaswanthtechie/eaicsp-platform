from app.services.carriers.base import CarrierAdapter
from app.schemas.shipment import (
    Carrier,
    Status,
    CarrierRate,
    TrackingInfo
)


class UPSAdapter(CarrierAdapter):

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
            estimated_days=4
        )

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