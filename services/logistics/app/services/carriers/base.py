from abc import ABC, abstractmethod

from app.schemas.shipment import CarrierRate, TrackingInfo


class CarrierAdapter(ABC):

    @abstractmethod
    def get_rate(
        self,
        origin: str,
        destination: str,
        weight_kg: float
    ) -> CarrierRate:
        pass

    @abstractmethod
    def get_tracking(
        self,
        tracking_number: str
    ) -> TrackingInfo:
        pass