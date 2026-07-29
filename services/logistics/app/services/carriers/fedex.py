from app.services.carriers.base import CarrierAdapter
from app.schemas.shipment import (
    Carrier,
    Status,
    CarrierRate,
    TrackingInfo
)


class FedExAdapter(CarrierAdapter):

    def get_rate(
        self,
        origin: str,
        destination: str,
        weight_kg: float
    ) -> CarrierRate:

        return CarrierRate(
            carrier=Carrier.fedex,
            origin=origin,
            destination=destination,
            weight_kg=weight_kg,
            price=950,
            estimated_days=3
        )

    def get_tracking(
        self,
        tracking_number: str
    ) -> TrackingInfo:

        return TrackingInfo(
            tracking_number=tracking_number,
            carrier=Carrier.fedex,
            status=Status.in_transit,
            location="In Transit",
            estimated_delivery=None
        )