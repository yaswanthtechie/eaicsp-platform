import re

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.supplier_risk import SupplierRiskScoreResponse


class SupplierRiskServiceError(Exception):
    """Base error for Supplier Risk Service integration."""


class SupplierRiskServiceUnavailableError(
    SupplierRiskServiceError
):
    """Raised when Supplier Risk Service cannot be reached."""


class SupplierRiskInvalidResponseError(
    SupplierRiskServiceError
):
    """Raised when Supplier Risk Service returns an invalid response."""


def _validate_risk_response(
    result: object,
    supplier_id: str,
) -> dict:
    """Validate the Supplier Risk API response using Pydantic."""

    if not isinstance(result, dict):
        raise SupplierRiskInvalidResponseError(
            "Supplier Risk Service returned an invalid response."
        )

    required_fields = {
        "supplier_id",
        "score",
        "tier",
        "top_factors",
        "top_evidence_articles",
        "computed_at",
    }

    if not required_fields.issubset(result):
        raise SupplierRiskInvalidResponseError(
            "Supplier Risk Service response is missing required fields."
        )

    try:
        validated = SupplierRiskScoreResponse.model_validate(result)

    except ValidationError as exc:
        raise SupplierRiskInvalidResponseError(
            "Supplier Risk Service returned an invalid response."
        ) from exc

    if validated.supplier_id != supplier_id:
        raise SupplierRiskInvalidResponseError(
            "Supplier Risk Service returned a different supplier ID."
        )

    return validated.model_dump(mode="json")


def get_supplier_risk_score(supplier_id: str) -> dict:
    """
    Retrieve the latest risk score for a supplier.

    Authentication is delegated to the Platform Service
    through the Supplier Portal service API key.
    """

    if not re.fullmatch(r"SUP-[0-9]{5}", supplier_id):
        raise ValueError("Invalid supplier ID format.")

    api_key = settings.SUPPLIER_PORTAL_SERVICE_API_KEY

    if not api_key:
        raise SupplierRiskServiceUnavailableError(
            "Supplier Portal service API key is not configured."
        )

    url = (
        f"{settings.SUPPLIER_RISK_SERVICE_URL.rstrip('/')}"
        f"/api/v1/suppliers/{supplier_id}/risk-score"
    )

    headers = {
        "X-API-Key": api_key,
    }

    try:
        with httpx.Client(
            timeout=settings.SUPPLIER_RISK_TIMEOUT_SECONDS
        ) as client:
            response = client.get(
                url,
                headers=headers,
            )

        response.raise_for_status()

    except httpx.TransportError as exc:
        raise SupplierRiskServiceUnavailableError(
            "Supplier Risk Service is unavailable."
        ) from exc

    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            raise SupplierRiskServiceUnavailableError(
                "Supplier Risk Service is unavailable."
            ) from exc

        raise SupplierRiskServiceError(
            "Supplier Risk Service returned an error."
        ) from exc

    try:
        result = response.json()

    except ValueError as exc:
        raise SupplierRiskInvalidResponseError(
            "Supplier Risk Service returned invalid JSON."
        ) from exc

    return _validate_risk_response(result, supplier_id)
