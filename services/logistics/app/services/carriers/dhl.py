from app.services.carriers.base import CarrierAdapter
from app.schemas.shipment import (
    Carrier,
    Status,
    CarrierRate,
    TrackingInfo
)


class DHLAdapter(CarrierAdapter):

    def get_rate(
        self,
        origin: str,
        destination: str,
        weight_kg: float
    ) -> CarrierRate:

        return CarrierRate(
            carrier=Carrier.dhl,
            origin=origin,
            destination=destination,
            weight_kg=weight_kg,
            price=850,
            estimated_days=2
        )


    def get_tracking(
        self,
        tracking_number: str
    ) -> TrackingInfo:

        return TrackingInfo(
            tracking_number=tracking_number,
            carrier=Carrier.dhl,
            status=Status.in_transit,
            location="In Transit",
            estimated_delivery=None
        )