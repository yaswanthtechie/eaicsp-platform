import requests

from dashboard.config import ANOMALY_SERVICE_URL


def detect_anomaly(payload: dict) -> dict:
    """Call the existing anomaly detection service."""

    response = requests.post(
        f"{ANOMALY_SERVICE_URL}/detect",
        json=payload,
        timeout=10,
    )

    response.raise_for_status()

    return response.json()