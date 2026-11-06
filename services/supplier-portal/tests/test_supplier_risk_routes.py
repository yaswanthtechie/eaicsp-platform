
import pytest

from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import verify_token

from app.services.supplier_risk_client import (
    SupplierRiskServiceError,
)


# ============================================================
# TEST USERS
# ============================================================

SUPPLIER_USER = {
    "valid": True,
    "user_id": 8,
    "email": "supplier@company.com",
    "full_name": "Supplier User",
    "role": "supplier",
    "supplier_id": "SUP-00001",
    "is_active": True,
}

SUPPLIER_B_USER = {
    "valid": True,
    "user_id": 99,
    "email": "supplierb@example.com",
    "full_name": "Supplier B",
    "role": "supplier",
    "supplier_id": "SUP-00002",
    "is_active": True,
}

SUPPLIER_NO_ID_USER = {
    "valid": True,
    "user_id": 100,
    "email": "supplier-no-id@example.com",
    "full_name": "Supplier Without ID",
    "role": "supplier",
    "supplier_id": None,
    "is_active": True,
}


# ============================================================
# MOCK SUPPLIER RISK RESPONSE
# ============================================================

VALID_RISK_RESPONSE = {
    "supplier_id": "SUP-00001",
    "score": 75.5,
    "tier": "High",
    "top_factors": [],
    "top_evidence_articles": [],
    "computed_at": "2026-11-05T05:00:00Z",
}


# ============================================================
# AUTHENTICATED TEST CLIENT
# ============================================================

class AuthenticatedTestClient:

    def __init__(self, client, user):
        self.client = client
        self.user = user

    def get(self, url, **kwargs):
        async def mock_verify_token():
            return self.user

        app.dependency_overrides[verify_token] = (
            mock_verify_token
        )

        return self.client.get(url, **kwargs)


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def client():
    app.dependency_overrides.clear()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def supplier_client(client):
    return AuthenticatedTestClient(
        client,
        SUPPLIER_USER,
    )


@pytest.fixture
def supplier_b_client(client):
    return AuthenticatedTestClient(
        client,
        SUPPLIER_B_USER,
    )


@pytest.fixture
def supplier_no_id_client(client):
    return AuthenticatedTestClient(
        client,
        SUPPLIER_NO_ID_USER,
    )


# ============================================================
# TEST: SUCCESSFUL RISK SCORE
# ============================================================

def test_get_supplier_risk_score_success(
    supplier_client,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.routes.supplier_risk.get_supplier",
        lambda supplier_id: object(),
    )

    monkeypatch.setattr(
        "app.routes.supplier_risk.get_supplier_risk_score",
        lambda supplier_id: VALID_RISK_RESPONSE,
    )

    response = supplier_client.get(
        "/api/v1/suppliers/SUP-00001/risk-score"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["supplier_id"] == "SUP-00001"
    assert data["risk_available"] is True
    assert data["score"] == 75.5
    assert data["tier"] == "High"
    assert data["top_factors"] == []
    assert data["top_evidence_articles"] == []


# ============================================================
# TEST: RISK SERVICE UNAVAILABLE
# ============================================================

def test_get_supplier_risk_score_unavailable(
    supplier_client,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.routes.supplier_risk.get_supplier",
        lambda supplier_id: object(),
    )

    def mock_risk_failure(supplier_id):
        raise SupplierRiskServiceError(
            "Supplier Risk Service unavailable"
        )

    monkeypatch.setattr(
        "app.routes.supplier_risk.get_supplier_risk_score",
        mock_risk_failure,
    )

    response = supplier_client.get(
        "/api/v1/suppliers/SUP-00001/risk-score"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["supplier_id"] == "SUP-00001"
    assert data["risk_available"] is False
    assert data["score"] is None
    assert data["tier"] is None
    assert data["top_factors"] == []
    assert data["top_evidence_articles"] == []
    assert data["computed_at"] is None


# ============================================================
# TEST: SUPPLIER CANNOT ACCESS ANOTHER SUPPLIER
# ============================================================

def test_supplier_cannot_access_another_supplier_risk(
    supplier_client,
    monkeypatch,
):
    response = supplier_client.get(
        "/api/v1/suppliers/SUP-00002/risk-score"
    )

    assert response.status_code == 403


# ============================================================
# TEST: SUPPLIER TOKEN WITHOUT SUPPLIER ID
# ============================================================

def test_supplier_without_supplier_id_is_forbidden(
    supplier_no_id_client,
):
    response = supplier_no_id_client.get(
        "/api/v1/suppliers/SUP-00001/risk-score"
    )

    assert response.status_code == 403


# ============================================================
# TEST: UNKNOWN SUPPLIER
# ============================================================

def test_unknown_supplier_returns_404(
    supplier_client,
    monkeypatch,
):
    def mock_supplier_not_found(supplier_id):
        raise ValueError("Supplier not found")

    monkeypatch.setattr(
        "app.routes.supplier_risk.get_supplier",
        mock_supplier_not_found,
    )

    response = supplier_client.get(
        "/api/v1/suppliers/SUP-00001/risk-score"
    )

    assert response.status_code == 404
