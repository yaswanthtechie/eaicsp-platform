from abc import ABC, abstractmethod
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.schemas.shipment import CarrierRate, TrackingInfo


def api_retry():
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )


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