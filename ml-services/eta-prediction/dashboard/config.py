import os


DEFAULT_ANOMALY_SERVICE_URL = "http://localhost:8000"


def anomaly_service_url() -> str:
    """
    Read the URL at call time (not import time), so changing
    ANOMALY_SERVICE_URL always takes effect and tests don't leak.
    """
    return os.getenv(
        "ANOMALY_SERVICE_URL",
        DEFAULT_ANOMALY_SERVICE_URL,
    ).rstrip("/")