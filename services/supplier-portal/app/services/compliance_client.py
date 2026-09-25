import httpx

from app.core.config import settings


class ComplianceServiceError(Exception):
    """Base error for Compliance Service integration."""


class ComplianceServiceUnavailableError(
    ComplianceServiceError
):
    """Raised when Compliance Service cannot be reached."""


class ComplianceBlockedError(Exception):
    """
    Raised when Compliance returned a valid decision
    that does not allow activation (BLOCK or REVIEW).

    Deliberately NOT a subclass of ComplianceServiceError:
    this is a business decision, not a service failure.
    """

    def __init__(self, decision: str, reason: str):
        self.decision = decision
        self.reason = reason

        super().__init__(
            f"Supplier activation blocked by Compliance Service. "
            f"Decision: {decision}. "
            f"Reason: {reason}"
        )


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

    except httpx.TransportError as exc:
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

    if not isinstance(result, dict):
        raise ComplianceServiceError(
            "Compliance Service returned an invalid response."
        )

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

    # Fail-closed: `decision` and `cleared` must agree.
    # CLEAR must come with cleared=True, and BLOCK/REVIEW
    # with cleared=False. A contradictory answer is treated
    # as an unusable response, never as a clearance.
    if cleared != (decision == "CLEAR"):
        raise ComplianceServiceError(
            "Compliance Service returned a contradictory decision."
        )

    return result