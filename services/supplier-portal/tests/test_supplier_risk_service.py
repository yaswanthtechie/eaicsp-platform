
import pytest

from app.services import supplier_risk_service
from app.services.supplier_risk_client import (
    SupplierRiskServiceError,
)


VALID_RISK_RESPONSE = {
    "supplier_id": "SUP-00001",
    "score": 75.5,
    "tier": "High",
    "top_factors": [],
    "top_evidence_articles": [],
    "computed_at": "2026-11-05T05:00:00Z",
}


def test_risk_score_success_returns_available_response(monkeypatch):
    monkeypatch.setattr(
        supplier_risk_service,
        "get_supplier_risk_score",
        lambda supplier_id: VALID_RISK_RESPONSE,
    )

    response = supplier_risk_service.get_supplier_risk_score_response(
        "SUP-00001"
    )

    assert response["supplier_id"] == "SUP-00001"
    assert response["risk_available"] is True
    assert response["score"] == 75.5
    assert response["tier"] == "High"


def test_risk_service_error_returns_fallback_response(monkeypatch):
    def mock_get_risk_score(supplier_id):
        raise SupplierRiskServiceError(
            "Supplier Risk Service unavailable"
        )

    monkeypatch.setattr(
        supplier_risk_service,
        "get_supplier_risk_score",
        mock_get_risk_score,
    )

    response = supplier_risk_service.get_supplier_risk_score_response(
        "SUP-00001"
    )

    assert response == {
        "supplier_id": "SUP-00001",
        "risk_available": False,
        "score": None,
        "tier": None,
        "top_factors": [],
        "top_evidence_articles": [],
        "computed_at": None,
    }


def test_none_score_returns_risk_unavailable(monkeypatch):
    risk_response = {
        **VALID_RISK_RESPONSE,
        "score": None,
        "tier": None,
    }

    monkeypatch.setattr(
        supplier_risk_service,
        "get_supplier_risk_score",
        lambda supplier_id: risk_response,
    )

    response = supplier_risk_service.get_supplier_risk_score_response(
        "SUP-00001"
    )

    assert response["risk_available"] is False
    assert response["score"] is None
    assert response["tier"] is None


def test_invalid_supplier_id_value_error_propagates(monkeypatch):
    def mock_get_risk_score(supplier_id):
        raise ValueError("Invalid supplier ID format.")

    monkeypatch.setattr(
        supplier_risk_service,
        "get_supplier_risk_score",
        mock_get_risk_score,
    )

    with pytest.raises(
        ValueError,
        match="Invalid supplier ID format.",
    ):
        supplier_risk_service.get_supplier_risk_score_response(
            "SUP001"
        )
