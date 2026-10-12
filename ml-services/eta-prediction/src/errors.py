"""
Errors that mean "the CALLER sent something we can't predict for".

Only these are returned as HTTP 422. Every other exception (a broken
calibration file, a geolocation file with missing columns, bad
coordinates in OUR data) is a server problem and becomes HTTP 500,
so a broken deployment is never reported as the caller's mistake.

Both subclass ValueError, so existing code and tests that catch
ValueError keep working.
"""


class InvalidPredictionRequest(ValueError):
    """The request itself is invalid. HTTP 422, INVALID_REQUEST."""


class LocationNotFound(InvalidPredictionRequest):
    """A city is not in the geolocation dataset. HTTP 422, LOCATION_NOT_FOUND."""