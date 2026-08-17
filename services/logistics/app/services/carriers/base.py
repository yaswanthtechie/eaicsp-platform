from abc import ABC, abstractmethod
from functools import wraps
from typing import Any, Callable, TypeVar

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.schemas.shipment import (
    Carrier,
    CarrierRate,
    TrackingInfo,
)


# ============================================================
# TYPE
# ============================================================

F = TypeVar(
    "F",
    bound=Callable[..., Any],
)


# ============================================================
# CARRIER ERROR
# ============================================================

class CarrierError(Exception):
    """
    Raised when a carrier API fails or is unavailable.
    """

    pass


# ============================================================
# RETRY CONFIGURATION
# ============================================================

def api_retry() -> Callable[[F], F]:
    """
    Retry a carrier API call up to 3 attempts.

    Retry sequence:

        Attempt 1 -> immediate
        Attempt 2 -> wait 1 second
        Attempt 3 -> wait 2 seconds

    Exponential backoff:

        1 second
        2 seconds
        4 seconds maximum

    Only CarrierError is retried.
    """

    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=4,
        ),
        retry=retry_if_exception_type(
            CarrierError
        ),
        reraise=True,
    )


# ============================================================
# BASE CARRIER
# ============================================================

class BaseCarrier(ABC):
    """
    Common interface for all carrier implementations.

    Every carrier must implement:

        get_rate()
        get_tracking()
    """

    carrier: Carrier

    base_price: float

    estimated_days: int

    # --------------------------------------------------------
    # RELIABILITY
    # --------------------------------------------------------

    # This is only a default class attribute.
    #
    # IMPORTANT:
    # R4 does NOT use this value as the final reliability
    # score.
    #
    # shipment_service.py calculates the real score from
    # carrier_history.
    reliability_score: float = 0.0

    # --------------------------------------------------------
    # GET RATE
    # --------------------------------------------------------

    @abstractmethod
    def get_rate(
        self,
        origin: str,
        destination: str,
        weight_kg: float,
    ) -> CarrierRate:
        """
        Return a shipping rate from the carrier.
        """

        raise NotImplementedError

    # --------------------------------------------------------
    # GET TRACKING
    # --------------------------------------------------------

    @abstractmethod
    def get_tracking(
        self,
        tracking_number: str,
    ) -> TrackingInfo:
        """
        Return tracking information from the carrier.
        """

        raise NotImplementedError