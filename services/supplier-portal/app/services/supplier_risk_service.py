
import logging

from app.services.supplier_risk_client import (
    get_supplier_risk_score,
    SupplierRiskServiceError,
)


logger = logging.getLogger(__name__)


def get_supplier_risk_score_response(
    supplier_id: str,
) -> dict:
    """
    Retrieve supplier risk information and build the API response.

    Risk is informational, so Supplier Risk Service failures
    return a fallback response instead of blocking onboarding.
    """

    try:
        risk_data = get_supplier_risk_score(supplier_id)

    except ValueError:
        # Invalid supplier ID format must be handled by the route.
        raise

    except SupplierRiskServiceError as exc:
        logger.warning(
            "Supplier risk unavailable for %s: %s",
            supplier_id,
            type(exc).__name__,
        )

        return {
            "supplier_id": supplier_id,
            "risk_available": False,
            "score": None,
            "tier": None,
            "top_factors": [],
            "top_evidence_articles": [],
            "computed_at": None,
        }

    return {
        **risk_data,
        "risk_available": risk_data["score"] is not None,
    }
