import requests

from dashboard.config import anomaly_service_url


class AnomalyServiceError(RuntimeError):
    """The anomaly service could not be reached or returned an error."""


def detect_anomaly(payload: dict) -> dict:
    """Call the existing anomaly detection service."""

    url = f"{anomaly_service_url()}/detect"

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=10,
        )
    except requests.RequestException as exc:
        raise AnomalyServiceError(
            f"Anomaly service is not reachable at {url}. "
            "Is it running? (see README)"
        ) from exc

    if not response.ok:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text

        raise AnomalyServiceError(
            f"Anomaly service returned {response.status_code}: {detail}"
        )

    return response.json()