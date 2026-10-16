"""
API tests for GET /api/v1/suppliers/{supplier_id}/risk-score.
Verifies strict adherence to contracts/openapi/supplier-risk.yaml:
- 200 OK with populated score, tier, top_factors, and evidence
- 200 OK with null score/tier when no recent evidence exists
- 422 Unprocessable Entity on non-canonical / invalid supplier IDs (e.g. SUP001)
- 404 Not Found on unknown canonical supplier IDs (e.g. SUP-99999)
- 401 Unauthorized on invalid authentication credentials
- 503 Service Unavailable on database/service failure
"""

from datetime import datetime, timezone
import os
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from pymongo.errors import ConnectionFailure

from src.analyze import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def mock_sentiment():
    """Mock FinBERT model initialization and sentiment to avoid test latency."""
    with patch("src.predict.analyze_sentiment") as mock_sa, \
         patch("src.analyze.init_model") as mock_im:
        mock_sa.return_value = {"label": "neutral", "confidence": 0.99}
        yield mock_sa, mock_im


# ----------------------------------------------------------------------
# 1. Valid Requests & Response Schema (200 OK)
# ----------------------------------------------------------------------

def test_get_risk_score_sanctioned_supplier_200(client):
    """
    SUP-00045 (TEST UN ENTITY 01) is sanctioned in master seed data.
    Must return 200 with critical tier, sanction risk factor, and legal category.
    """
    response = client.get("/api/v1/suppliers/SUP-00045/risk-score")
    assert response.status_code == 200
    data = response.json()

    # Required contract fields
    assert "score" in data
    assert "tier" in data
    assert "top_factors" in data
    assert "top_evidence_articles" in data
    assert "computed_at" in data

    assert data["score"] is not None
    assert data["score"] >= 80.0
    assert data["tier"] in ("High", "Critical")

    # Factors schema
    assert len(data["top_factors"]) > 0
    factor = data["top_factors"][0]
    assert factor["factor"] == "sanction"
    assert factor["category"] == "Legal"
    assert factor["weight"] > 0
    assert "description" in factor

    # Evidence articles schema
    assert len(data["top_evidence_articles"]) > 0
    article = data["top_evidence_articles"][0]
    assert "headline" in article
    assert "date" in article
    assert article["sentiment"] in ("positive", "neutral", "negative")
    assert "score" in article
    assert len(article["signals"]) > 0
    assert article["signals"][0]["keyword"] == "sanction"


def test_get_risk_score_no_recent_evidence_returns_null_score(client):
    """
    Contract specification:
    'When no recent evidence is available, score and tier may be null.'
    """
    response = client.get("/api/v1/suppliers/SUP-00019/risk-score")
    assert response.status_code == 200
    data = response.json()

    assert data["score"] is None
    assert data["tier"] is None
    assert data["top_factors"] == []
    assert data["top_evidence_articles"] == []
    assert isinstance(data["computed_at"], str)


def test_get_risk_score_persisted_mongodb_document(client):
    """When a pre-computed assessment exists in MongoDB, it is returned directly."""
    mock_doc = {
        "supplier_id": "SUP-00031",
        "supplier_name": "Apex Industries Pvt Ltd",
        "score": 64.5,
        "tier": "Medium",
        "top_factors": [
            {
                "factor": "strike",
                "category": "Operational",
                "weight": 35.0,
                "description": "Labor strike disruption.",
            }
        ],
        "top_evidence_articles": [
            {
                "headline": "Apex Industries faces workforce strike.",
                "date": "2026-10-10",
                "sentiment": "negative",
                "score": 64.5,
                "signals": [{"keyword": "strike", "weight": 35.0}],
            }
        ],
        "computed_at": "2026-10-15T09:00:00Z",
    }

    with patch("src.analyze.fetch_risk_assessment", return_value=mock_doc):
        response = client.get("/api/v1/suppliers/SUP-00031/risk-score")
        assert response.status_code == 200
        data = response.json()
        assert data["score"] == 64.5
        assert data["tier"] == "Medium"
        assert len(data["top_factors"]) == 1
        assert data["top_factors"][0]["factor"] == "strike"
        assert data["computed_at"] == "2026-10-15T09:00:00Z"


# ----------------------------------------------------------------------
# 2. Invalid Identifier Validation (422 Unprocessable Entity)
# ----------------------------------------------------------------------

def test_legacy_inventory_id_returns_422(client):
    """Legacy inventory ID format SUP001 must be rejected with 422."""
    response = client.get("/api/v1/suppliers/SUP001/risk-score")
    assert response.status_code == 422


def test_legacy_inventory_id_sup045_returns_422(client):
    """Legacy inventory ID format SUP045 must be rejected with 422."""
    response = client.get("/api/v1/suppliers/SUP045/risk-score")
    assert response.status_code == 422


def test_malformed_supplier_ids_return_422(client):
    for bad_id in ["invalid", "SUP-1", "SUP-1234", "SUP-123456", "sup-00045"]:
        res = client.get(f"/api/v1/suppliers/{bad_id}/risk-score")
        assert res.status_code == 422, f"Expected 422 for {bad_id}, got {res.status_code}"


# ----------------------------------------------------------------------
# 3. Unknown Supplier (404 Not Found)
# ----------------------------------------------------------------------

def test_unknown_canonical_supplier_returns_404(client):
    """A syntactically valid ID that does not exist in master data returns 404."""
    response = client.get("/api/v1/suppliers/SUP-99999/risk-score")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ----------------------------------------------------------------------
# 4. Authentication (401 Unauthorized)
# ----------------------------------------------------------------------

def test_invalid_bearer_token_returns_401(client):
    response = client.get(
        "/api/v1/suppliers/SUP-00045/risk-score",
        headers={"Authorization": "Bearer invalid"},
    )
    assert response.status_code == 401
    assert "authentication credentials" in response.json()["detail"].lower()


def test_malformed_auth_header_returns_401(client):
    response = client.get(
        "/api/v1/suppliers/SUP-00045/risk-score",
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
    )
    assert response.status_code == 401


def test_missing_auth_when_enforced_returns_401(client):
    with patch.dict(os.environ, {"SUPPLIER_RISK_REQUIRE_AUTH": "true"}):
        response = client.get("/api/v1/suppliers/SUP-00045/risk-score")
        assert response.status_code == 401


def test_valid_bearer_token_succeeds(client):
    response = client.get(
        "/api/v1/suppliers/SUP-00045/risk-score",
        headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.valid_token"},
    )
    assert response.status_code == 200


# ----------------------------------------------------------------------
# 5. Service Unavailable (503 Service Unavailable)
# ----------------------------------------------------------------------

def test_service_unavailable_env_toggle_503(client):
    with patch.dict(os.environ, {"SUPPLIER_RISK_UNAVAILABLE": "1"}):
        response = client.get("/api/v1/suppliers/SUP-00045/risk-score")
        assert response.status_code == 503
        assert "temporarily unavailable" in response.json()["detail"]


def test_mongodb_connection_failure_returns_503(client):
    with patch("src.analyze.resolve_canonical_supplier", side_effect=ConnectionFailure("Mongo unreachable")):
        response = client.get("/api/v1/suppliers/SUP-00045/risk-score")
        assert response.status_code == 503


# ----------------------------------------------------------------------
# 6. Gateway Route Rewrite Aliases
# ----------------------------------------------------------------------

def test_gateway_alias_routes_work(client):
    # Both paths must resolve cleanly
    res1 = client.get("/api/v1/suppliers/SUP-00045/risk-score")
    res2 = client.get("/api/v1/supplier-risk/SUP-00045/risk-score")
    res3 = client.get("/api/v1/supplier-risk/suppliers/SUP-00045/risk-score")

    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res3.status_code == 200
    assert res1.json()["tier"] == res2.json()["tier"]


# ----------------------------------------------------------------------
# 7. Seed Mappings Administration Endpoint
# ----------------------------------------------------------------------

def test_post_seed_mappings_endpoint(client):
    response = client.post("/api/v1/supplier-risk/seed-mappings")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "stats" in data
