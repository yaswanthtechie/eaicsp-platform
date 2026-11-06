
import re
from datetime import date, datetime

import httpx

from app.core.config import settings


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


def _is_number(value: object) -> bool:
    """Return True for numeric values, excluding booleans."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_risk_response(
    result: object,
    supplier_id: str,
) -> dict:
    """Validate the Supplier Risk API response against its contract."""

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

    if result["supplier_id"] != supplier_id:
        raise SupplierRiskInvalidResponseError(
            "Supplier Risk Service returned a different supplier ID."
        )

    score = result["score"]
    tier = result["tier"]

    if score is not None:
        if not _is_number(score) or not 0 <= score <= 100:
            raise SupplierRiskInvalidResponseError(
                "Supplier Risk Service returned an invalid risk score."
            )

    if tier not in {
        "Low",
        "Medium",
        "High",
        "Critical",
        None,
    }:
        raise SupplierRiskInvalidResponseError(
            "Supplier Risk Service returned an invalid risk tier."
        )

    if (score is None) != (tier is None):
        raise SupplierRiskInvalidResponseError(
            "Supplier Risk Service returned an inconsistent score and tier."
        )

    factors = result["top_factors"]
    articles = result["top_evidence_articles"]

    if not isinstance(factors, list) or not isinstance(articles, list):
        raise SupplierRiskInvalidResponseError(
            "Supplier Risk Service returned invalid evidence collections."
        )

    if score is None and (factors or articles):
        raise SupplierRiskInvalidResponseError(
            "Supplier Risk Service returned evidence without a risk score."
        )

    for factor in factors:
        if not isinstance(factor, dict):
            raise SupplierRiskInvalidResponseError(
                "Supplier Risk Service returned an invalid risk factor."
            )

        if not {
            "factor",
            "category",
            "weight",
            "description",
        }.issubset(factor):
            raise SupplierRiskInvalidResponseError(
                "Supplier Risk Service returned an incomplete risk factor."
            )

        if not isinstance(factor["factor"], str):
            raise SupplierRiskInvalidResponseError(
                "Supplier Risk Service returned an invalid factor name."
            )

        if factor["category"] not in {
            "Financial",
            "Operational",
            "Reputational",
            "Security",
        }:
            raise SupplierRiskInvalidResponseError(
                "Supplier Risk Service returned an invalid factor category."
            )

        if not _is_number(factor["weight"]):
            raise SupplierRiskInvalidResponseError(
                "Supplier Risk Service returned an invalid factor weight."
            )

        if not isinstance(factor["description"], str):
            raise SupplierRiskInvalidResponseError(
                "Supplier Risk Service returned an invalid factor description."
            )

    for article in articles:
        if not isinstance(article, dict):
            raise SupplierRiskInvalidResponseError(
                "Supplier Risk Service returned an invalid evidence article."
            )

        if not {
            "headline",
            "date",
            "sentiment",
            "score",
            "signals",
        }.issubset(article):
            raise SupplierRiskInvalidResponseError(
                "Supplier Risk Service returned an incomplete evidence article."
            )

        if not isinstance(article["headline"], str):
            raise SupplierRiskInvalidResponseError(
                "Supplier Risk Service returned an invalid article headline."
            )

        article_date = article["date"]
        if article_date is not None:
            try:
                date.fromisoformat(article_date)
            except (TypeError, ValueError) as exc:
                raise SupplierRiskInvalidResponseError(
                    "Supplier Risk Service returned an invalid article date."
                ) from exc

        if article["sentiment"] not in {
            "positive",
            "neutral",
            "negative",
        }:
            raise SupplierRiskInvalidResponseError(
                "Supplier Risk Service returned an invalid article sentiment."
            )

        article_score = article["score"]
        if (
            not _is_number(article_score)
            or not 0 <= article_score <= 100
        ):
            raise SupplierRiskInvalidResponseError(
                "Supplier Risk Service returned an invalid article score."
            )

        signals = article["signals"]
        if not isinstance(signals, list):
            raise SupplierRiskInvalidResponseError(
                "Supplier Risk Service returned invalid article signals."
            )

        for signal in signals:
            if not isinstance(signal, dict):
                raise SupplierRiskInvalidResponseError(
                    "Supplier Risk Service returned an invalid evidence signal."
                )

            if not {"keyword", "weight"}.issubset(signal):
                raise SupplierRiskInvalidResponseError(
                    "Supplier Risk Service returned an incomplete evidence signal."
                )

            if not isinstance(signal["keyword"], str):
                raise SupplierRiskInvalidResponseError(
                    "Supplier Risk Service returned an invalid signal keyword."
                )

            if not _is_number(signal["weight"]):
                raise SupplierRiskInvalidResponseError(
                    "Supplier Risk Service returned an invalid signal weight."
                )

    computed_at = result["computed_at"]
    if not isinstance(computed_at, str):
        raise SupplierRiskInvalidResponseError(
            "Supplier Risk Service returned an invalid computation timestamp."
        )

    try:
        datetime.fromisoformat(computed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SupplierRiskInvalidResponseError(
            "Supplier Risk Service returned an invalid computation timestamp."
        ) from exc

    return result


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
        with httpx.Client(timeout=5.0) as client:
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
