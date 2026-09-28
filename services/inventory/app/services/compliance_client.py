import httpx

from app.core.config import settings


VALID_DECISIONS = {
    "CLEAR",
    "BLOCK",
    "REVIEW",
}


class ComplianceServiceError(Exception):
    """Base error for Compliance Service integration."""


class ComplianceServiceUnavailableError(
    ComplianceServiceError
):
    """Raised when Compliance Service cannot be reached."""


class ComplianceBlockedError(Exception):
    """
    Raised when Compliance returned a valid BLOCK or REVIEW
    decision for the selected supplier.

    Deliberately NOT a subclass of ComplianceServiceError:
    this is a business decision, not a service failure.
    """

    def __init__(
        self,
        supplier_id: str,
        decision: str,
        reason: str,
    ):
        self.supplier_id = supplier_id
        self.decision = decision
        self.reason = reason

        super().__init__(
            f"Supplier {supplier_id} not cleared by "
            f"Compliance Service. Decision: {decision}. "
            f"Reason: {reason}"
        )


def check_supplier_compliance(
    supplier_id: str,
    supplier_name: str,
    country: str,
) -> dict:
    """
    Call Compliance Service before creating
    an automatic purchase order.
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
        "X-Caller-Service": "inventory-service",
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
        # Covers timeouts, refused connections and
        # other network failures.
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

    if decision not in VALID_DECISIONS:
        raise ComplianceServiceError(
            "Compliance Service returned an invalid decision."
        )

    if not isinstance(cleared, bool):
        raise ComplianceServiceError(
            "Compliance Service returned an invalid clearance value."
        )

    # Fail-closed: CLEAR must come with cleared=True and
    # BLOCK/REVIEW with cleared=False. A contradictory
    # answer is unusable, never a clearance.
    if cleared != (decision == "CLEAR"):
        raise ComplianceServiceError(
            "Compliance Service returned a contradictory decision."
        )

    return result