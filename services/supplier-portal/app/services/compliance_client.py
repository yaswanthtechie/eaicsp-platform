import httpx

from app.core.config import settings


class ComplianceServiceError(Exception):
    """Base error for Compliance Service integration."""


class ComplianceServiceUnavailableError(
    ComplianceServiceError
):
    """Raised when Compliance Service cannot be reached."""


def check_supplier_compliance(
    supplier_id: str,
    supplier_name: str,
    country: str,
) -> dict:
    """
    Call the Compliance Service to screen a supplier
    before supplier activation.

    This is a business-data integration. Authentication
    remains delegated to the Platform Service.
    """

    url = (
        f"{settings.COMPLIANCE_SERVICE_URL.rstrip('/')}"
        "/api/v1/compliance/internal-check"
    )

    payload = {
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "country": country,
    }

    headers = {
        "X-Caller-Service": "supplier-portal",
    }

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(
                url,
                json=payload,
                headers=headers,
            )

        response.raise_for_status()

    except (
        httpx.TimeoutException,
        httpx.ConnectError,
        httpx.NetworkError,
    ) as exc:
        raise ComplianceServiceUnavailableError(
            "Compliance Service is unavailable."
        ) from exc

    except httpx.HTTPStatusError as exc:
        raise ComplianceServiceError(
            "Compliance Service returned an error."
        ) from exc

    try:
        result = response.json()
    except ValueError as exc:
        raise ComplianceServiceError(
            "Compliance Service returned an invalid response."
        ) from exc

    decision = result.get("decision")
    cleared = result.get("cleared")

    if decision not in {
        "CLEAR",
        "BLOCK",
        "REVIEW",
    }:
        raise ComplianceServiceError(
            "Compliance Service returned an invalid decision."
        )

    if not isinstance(cleared, bool):
        raise ComplianceServiceError(
            "Compliance Service returned an invalid clearance value."
        )

    return result
