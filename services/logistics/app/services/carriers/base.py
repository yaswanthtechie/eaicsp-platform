from abc import ABC, abstractmethod

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


# ============================================================
# CARRIER ERROR
# ============================================================

class CarrierError(Exception):
    """
    Exception raised when a carrier API operation fails.
    """

    pass


# ============================================================
# RETRY DECORATOR
# ============================================================

def api_retry():
    """
    Retry carrier API calls up to 3 times.

    Retry pattern:

        Attempt 1
        Wait 1 second
        Attempt 2
        Wait 2 seconds
        Attempt 3

    Retry happens only for CarrierError.
    """

    return retry(
        retry=retry_if_exception_type(
            CarrierError
        ),
        stop=stop_after_attempt(3),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=4,
        ),
        reraise=True,
    )


# ============================================================
# BASE CARRIER
# ============================================================

class BaseCarrier(ABC):
    """
    Base class for all carrier adapters.

    Every carrier must implement:

        get_rate()
        get_tracking()
    """

    @abstractmethod
    def get_rate(
        self,
        origin: str,
        destination: str,
        weight_kg: float,
    ):
        """
        Return the shipping rate for the carrier.
        """
        raise NotImplementedError

    @abstractmethod
    def get_tracking(
        self,
        tracking_number: str,
    ):
        """
        Return tracking information for a shipment.
        """
        raise NotImplementedError