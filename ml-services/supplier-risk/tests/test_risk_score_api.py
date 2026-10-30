"""
API tests for GET /api/v1/suppliers/{supplier_id}/risk-score and POST /seed-mappings.
Verifies strict adherence to contracts/openapi/supplier-risk.yaml, Fix 3, and Fix 4:
- 200 OK with populated score, tier, top_factors, and evidence
- 200 OK with null score/tier when no recent evidence exists
- 422 Unprocessable Entity on non-canonical / invalid supplier IDs (e.g. SUP001)
- 404 Not Found on unknown canonical supplier IDs (e.g. SUP-99999)
- 401 Unauthorized on missing, invalid, or unverified authentication credentials
- 503 Service Unavailable on database/service failure or platform auth timeout
- Idempotent and fresh risk assessment persistence and TTL caching
"""

from datetime import datetime, timedelta, timezone
import os
from unittest.mock import MagicMock, patch
import httpx
from pymongo.errors import ConnectionFailure, PyMongoError
import pytest
from fastapi.testclient import TestClient

from src.analyze import (
    RISK_ASSESSMENT_TTL_SECONDS,
    EvidenceArticle,
    EvidenceSignal,
    RiskFactor,
    SIGNAL_CATEGORIES,
    SupplierRiskScoreResponse,
    _is_fresh,
    _save_assessment,
    app,
    compute_canonical_supplier_risk_score,
    get_risk_assessment_ttl_seconds,
    require_caller,
)
from src.config import Settings, get_settings, validate_risk_assessment_ttl_seconds


VALID_SERVICE_CONFIG = "supplier-portal:valid-secret-key,inventory-service:inv-key-999"
VALID_SERVICE_HEADERS = {
    "X-Caller-Service": "supplier-portal",
    "X-Service-Key": "valid-secret-key",
}


@pytest.fixture
def client():
    """Default test client overrides require_caller so ordinary API tests do not depend on Platform authentication."""
    app.dependency_overrides[require_caller] = lambda: "test-caller"
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(require_caller, None)


@pytest.fixture
def raw_client():
    """Raw client that does not override require_caller, exercising real authentication."""
    app.dependency_overrides.pop(require_caller, None)
    with TestClient(app) as test_client:
        yield test_client



@pytest.fixture(autouse=True)
def default_auth_env(monkeypatch):
    """Set standard service keys for API tests so general endpoint assertions succeed."""
    monkeypatch.setenv("SUPPLIER_RISK_SERVICE_KEYS", VALID_SERVICE_CONFIG)


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
    Must return 200 with critical tier, sanction risk factor with Security category,
    exact description 'Designated on UN-SC (seed master data).', and empty evidence articles.
    """
    with patch("src.analyze.fetch_risk_assessment", return_value=None):
        response = client.get("/api/v1/suppliers/SUP-00045/risk-score", headers=VALID_SERVICE_HEADERS)
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
        assert factor["category"] == "Security"
        assert factor["weight"] > 0
        assert factor["description"] == "Designated on UN-SC (seed master data)."

        # Evidence articles schema - no fabricated articles for sanctioned supplier
        assert data["top_evidence_articles"] == []


def test_get_risk_score_no_recent_evidence_returns_null_score(client):
    """
    Contract specification:
    'When no recent evidence is available, score and tier may be null.'
    """
    response = client.get("/api/v1/suppliers/SUP-00019/risk-score", headers=VALID_SERVICE_HEADERS)
    assert response.status_code == 200
    data = response.json()

    assert data["score"] is None
    assert data["tier"] is None
    assert data["top_factors"] == []
    assert data["top_evidence_articles"] == []
    assert isinstance(data["computed_at"], str)


def test_get_risk_score_persisted_mongodb_document(client):
    """When a fresh pre-computed assessment exists in MongoDB, it is returned directly."""
    fresh_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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
        "computed_at": fresh_time,
    }

    with patch("src.analyze.fetch_risk_assessment", return_value=mock_doc):
        response = client.get("/api/v1/suppliers/SUP-00031/risk-score", headers=VALID_SERVICE_HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert data["score"] == 64.5
        assert data["tier"] == "Medium"
        assert len(data["top_factors"]) == 1
        assert data["top_factors"][0]["factor"] == "strike"
        assert data["computed_at"] == fresh_time


# ----------------------------------------------------------------------
# 2. Invalid Identifier Validation (422 Unprocessable Entity)
# ----------------------------------------------------------------------

def test_legacy_inventory_id_returns_422(client):
    """Legacy inventory ID format SUP001 must be rejected with 422."""
    response = client.get("/api/v1/suppliers/SUP001/risk-score", headers=VALID_SERVICE_HEADERS)
    assert response.status_code == 422


def test_legacy_inventory_id_sup045_returns_422(client):
    """Legacy inventory ID format SUP045 must be rejected with 422."""
    response = client.get("/api/v1/suppliers/SUP045/risk-score", headers=VALID_SERVICE_HEADERS)
    assert response.status_code == 422


def test_malformed_supplier_ids_return_422(client):
    for bad_id in ["invalid", "SUP-1", "SUP-1234", "SUP-123456", "sup-00045"]:
        res = client.get(f"/api/v1/suppliers/{bad_id}/risk-score", headers=VALID_SERVICE_HEADERS)
        assert res.status_code == 422, f"Expected 422 for {bad_id}, got {res.status_code}"


# ----------------------------------------------------------------------
# 3. Unknown Supplier (404 Not Found)
# ----------------------------------------------------------------------

def test_unknown_canonical_supplier_returns_404(client):
    """A syntactically valid ID that does not exist in master data returns 404."""
    response = client.get("/api/v1/suppliers/SUP-99999/risk-score", headers=VALID_SERVICE_HEADERS)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ----------------------------------------------------------------------
# 4. Service Unavailable (503 Service Unavailable)
# ----------------------------------------------------------------------

def test_mongodb_failure_during_canonical_lookup_returns_503(client):
    """MongoDB failure during canonical supplier lookup returns HTTP 503, never 404."""
    with patch("src.analyze.resolve_canonical_supplier", side_effect=PyMongoError("Mongo unreachable")):
        response = client.get("/api/v1/suppliers/SUP-00045/risk-score", headers=VALID_SERVICE_HEADERS)
        assert response.status_code == 503
        assert "temporarily unavailable" in response.json()["detail"].lower()


def test_mongodb_failure_during_assessment_retrieval_returns_503(client):
    """MongoDB failure during risk assessment retrieval returns HTTP 503."""
    with patch("src.analyze.fetch_risk_assessment", side_effect=PyMongoError("Connection timed out")):
        response = client.get("/api/v1/suppliers/SUP-00045/risk-score", headers=VALID_SERVICE_HEADERS)
        assert response.status_code == 503
        assert "temporarily unavailable" in response.json()["detail"].lower()


def test_mongodb_failure_during_trend_headline_loading_returns_503(client):
    """MongoDB failure during trend-headline loading returns HTTP 503."""
    with patch("src.analyze.fetch_risk_assessment", return_value=None), \
         patch("src.analyze.load_active_trend_headlines", side_effect=PyMongoError("Mongo collection failure")):
        response = client.get("/api/v1/suppliers/SUP-00019/risk-score", headers=VALID_SERVICE_HEADERS)
        assert response.status_code == 503
        assert "temporarily unavailable" in response.json()["detail"].lower()


def test_runtime_error_during_trend_headline_loading_returns_503(client):
    """Data loading runtime error (e.g. empty/unreachable Mongo) returns HTTP 503."""
    with patch("src.analyze.fetch_risk_assessment", return_value=None), \
         patch("src.analyze.load_active_trend_headlines", side_effect=RuntimeError("MongoDB query failed")):
        response = client.get("/api/v1/suppliers/SUP-00019/risk-score", headers=VALID_SERVICE_HEADERS)
        assert response.status_code == 503
        assert "temporarily unavailable" in response.json()["detail"].lower()


def test_simulated_mongodb_failure_returns_503_for_supplier_sup00019(client):
    """Simulated MongoDB failure returns HTTP 503 for supplier SUP-00019."""
    with patch("src.analyze.resolve_canonical_supplier", side_effect=PyMongoError("Mongo connection lost")):
        response = client.get("/api/v1/suppliers/SUP-00019/risk-score")
        assert response.status_code == 503
        assert "temporarily unavailable" in response.json()["detail"].lower()


def test_database_failures_not_converted_into_404_or_empty_evidence(client):
    """Database failures must not be converted into HTTP 404 or an empty-evidence response."""
    # Failure in supplier resolution must return 503, never 404
    with patch("src.analyze.resolve_canonical_supplier", side_effect=PyMongoError("Mongo unavailable")):
        res_lookup = client.get("/api/v1/suppliers/SUP-00019/risk-score")
        assert res_lookup.status_code == 503
        assert res_lookup.status_code != 404
        assert res_lookup.status_code != 200

    # Failure in assessment retrieval must return 503, never 200 with empty evidence
    with patch("src.analyze.fetch_risk_assessment", side_effect=PyMongoError("Mongo unavailable")):
        res_fetch = client.get("/api/v1/suppliers/SUP-00019/risk-score")
        assert res_fetch.status_code == 503
        assert res_fetch.status_code != 404
        assert res_fetch.status_code != 200



# ----------------------------------------------------------------------
# 5. Gateway Route Rewrite Aliases
# ----------------------------------------------------------------------

def test_gateway_alias_routes_work(client):
    res1 = client.get("/api/v1/suppliers/SUP-00045/risk-score", headers=VALID_SERVICE_HEADERS)
    res2 = client.get("/api/v1/supplier-risk/SUP-00045/risk-score", headers=VALID_SERVICE_HEADERS)
    res3 = client.get("/api/v1/supplier-risk/suppliers/SUP-00045/risk-score", headers=VALID_SERVICE_HEADERS)

    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res3.status_code == 200
    assert res1.json()["tier"] == res2.json()["tier"]


# ----------------------------------------------------------------------
# 6. Fix 3: Authentication Fail-Closed Tests (Section D)
# ----------------------------------------------------------------------

def test_missing_credentials_returns_401(raw_client):
    """Requests with no credentials must always receive HTTP 401."""
    res = raw_client.get("/api/v1/suppliers/SUP-00045/risk-score")
    assert res.status_code == 401
    assert "authentication credentials" in res.json()["detail"].lower()


def test_valid_service_caller_and_key_accepted(raw_client):
    """Supplier Portal / Service caller with valid key is accepted."""
    res = raw_client.get("/api/v1/suppliers/SUP-00045/risk-score", headers=VALID_SERVICE_HEADERS)
    assert res.status_code == 200


def test_missing_service_key_returns_401(raw_client):
    """Caller provided without secret key receives 401."""
    res = raw_client.get(
        "/api/v1/suppliers/SUP-00045/risk-score",
        headers={"X-Caller-Service": "supplier-portal"},
    )
    assert res.status_code == 401


def test_incorrect_service_key_returns_401(raw_client):
    """Caller provided with incorrect secret key receives 401."""
    res = raw_client.get(
        "/api/v1/suppliers/SUP-00045/risk-score",
        headers={"X-Caller-Service": "supplier-portal", "X-Service-Key": "wrong-secret-key"},
    )
    assert res.status_code == 401


def test_unknown_service_caller_returns_401(raw_client):
    """Unknown service name not in SUPPLIER_RISK_SERVICE_KEYS receives 401."""
    res = raw_client.get(
        "/api/v1/suppliers/SUP-00045/risk-score",
        headers={"X-Caller-Service": "unknown-service", "X-Service-Key": "valid-secret-key"},
    )
    assert res.status_code == 401


def test_empty_credentials_return_401(raw_client):
    """Whitespace or empty credentials must fail closed with 401."""
    res1 = raw_client.get(
        "/api/v1/suppliers/SUP-00045/risk-score",
        headers={"X-Caller-Service": "   ", "X-Service-Key": "   "},
    )
    assert res1.status_code == 401

    res2 = raw_client.get(
        "/api/v1/suppliers/SUP-00045/risk-score",
        headers={"Authorization": "Bearer   "},
    )
    assert res2.status_code == 401


def test_malformed_auth_header_returns_401(raw_client):
    """Non-Bearer schemes (e.g. Basic) receive 401."""
    res = raw_client.get(
        "/api/v1/suppliers/SUP-00045/risk-score",
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
    )
    assert res.status_code == 401


def test_valid_bearer_jwt_with_platform_200_accepted(raw_client):
    """Valid Bearer JWT verified with Platform 200 permits the request."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"valid": True, "email": "alice@company.com", "user_id": 101}

    with patch("httpx.post", return_value=mock_resp) as mock_post:
        res = raw_client.get(
            "/api/v1/suppliers/SUP-00045/risk-score",
            headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.valid-jwt-token"},
        )
        assert res.status_code == 200
        assert mock_post.called
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["timeout"] == 2.0


def test_platform_401_becomes_supplier_risk_401(raw_client):
    """Platform returning 401 must become HTTP 401 from Supplier Risk."""
    mock_resp = MagicMock(status_code=401)
    with patch("httpx.post", return_value=mock_resp):
        res = raw_client.get(
            "/api/v1/suppliers/SUP-00045/risk-score",
            headers={"Authorization": "Bearer expired-token"},
        )
        assert res.status_code == 401


def test_platform_403_becomes_supplier_risk_401(raw_client):
    """Platform returning 403 must become HTTP 401 from Supplier Risk."""
    mock_resp = MagicMock(status_code=403)
    with patch("httpx.post", return_value=mock_resp):
        res = raw_client.get(
            "/api/v1/suppliers/SUP-00045/risk-score",
            headers={"Authorization": "Bearer forbidden-token"},
        )
        assert res.status_code == 401


def test_platform_timeout_returns_503(raw_client):
    """Platform verification timeout returns HTTP 503."""
    with patch("httpx.post", side_effect=httpx.TimeoutException("Platform timeout")):
        res = raw_client.get(
            "/api/v1/suppliers/SUP-00045/risk-score",
            headers={"Authorization": "Bearer some-token"},
        )
        assert res.status_code == 503
        assert "temporarily unavailable" in res.json()["detail"].lower() or "timed out" in res.json()["detail"].lower()


def test_platform_network_failure_returns_503(raw_client):
    """Platform network failure returns HTTP 503."""
    with patch("httpx.post", side_effect=httpx.RequestError("Connection refused")):
        res = raw_client.get(
            "/api/v1/suppliers/SUP-00045/risk-score",
            headers={"Authorization": "Bearer some-token"},
        )
        assert res.status_code == 503


def test_platform_unreachable_returns_503(raw_client):
    """If Platform is unreachable (ConnectTimeout/NetworkError), API returns HTTP 503."""
    with patch("httpx.post", side_effect=httpx.ConnectError("Platform unreachable")):
        res = raw_client.get(
            "/api/v1/suppliers/SUP-00045/risk-score",
            headers={"Authorization": "Bearer some-token"},
        )
        assert res.status_code == 503
        assert "unavailable" in res.json()["detail"].lower()


def test_unexpected_platform_response_fails_closed(raw_client):
    """Other unexpected Platform responses (e.g. 500, 502, 400) must fail closed with 401."""
    for bad_status in [500, 502, 400, 404]:
        mock_resp = MagicMock(status_code=bad_status)
        with patch("httpx.post", return_value=mock_resp):
            res = raw_client.get(
                "/api/v1/suppliers/SUP-00045/risk-score",
                headers={"Authorization": "Bearer some-token"},
            )
            assert res.status_code == 401
            assert res.status_code != 200


def test_platform_200_with_valid_false_fails_closed(raw_client):
    """Platform 200 with valid=False indicates invalid token; fails closed with 401."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"valid": False, "error": "Token revoked"}

    with patch("httpx.post", return_value=mock_resp):
        res = raw_client.get(
            "/api/v1/suppliers/SUP-00045/risk-score",
            headers={"Authorization": "Bearer revoked-token"},
        )
        assert res.status_code == 401


def test_platform_invalid_json_fails_closed(raw_client):
    """Non-JSON response from Platform fails closed with 401."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.side_effect = ValueError("Invalid JSON response")

    with patch("httpx.post", return_value=mock_resp):
        res = raw_client.get(
            "/api/v1/suppliers/SUP-00045/risk-score",
            headers={"Authorization": "Bearer some-token"},
        )
        assert res.status_code == 401


def test_post_seed_mappings_requires_authentication(raw_client):
    """POST /seed-mappings requires authentication and rejects unauthenticated callers."""
    res_no_auth = raw_client.post("/api/v1/supplier-risk/seed-mappings")
    assert res_no_auth.status_code == 401

    res_auth = raw_client.post("/api/v1/supplier-risk/seed-mappings", headers=VALID_SERVICE_HEADERS)
    assert res_auth.status_code == 200
    assert res_auth.json()["status"] == "ok"


def test_seed_mappings_without_authentication_returns_401(raw_client):
    """The seed-mappings endpoint without authentication returns HTTP 401."""
    res = raw_client.post("/api/v1/supplier-risk/seed-mappings")
    assert res.status_code == 401


def test_post_seed_mappings_safe_error_handling(client):
    """POST /seed-mappings must not leak raw exception text to clients."""
    with patch("src.analyze.seed_supplier_mappings", side_effect=RuntimeError("Sensitive DB mongodb://user:pass@10.0.1.5:27017")):
        res = client.post("/api/v1/supplier-risk/seed-mappings", headers=VALID_SERVICE_HEADERS)
        assert res.status_code == 500
        detail = res.json()["detail"]
        assert "mongodb://" not in detail
        assert "user:pass" not in detail
        assert detail == "Failed seeding supplier mappings."


def test_old_environment_bypass_no_longer_permits_access(raw_client, monkeypatch):
    """Setting SUPPLIER_RISK_REQUIRE_AUTH=false no longer bypasses authentication."""
    monkeypatch.setenv("SUPPLIER_RISK_REQUIRE_AUTH", "false")
    res = raw_client.get("/api/v1/suppliers/SUP-00045/risk-score")
    assert res.status_code == 401


def test_magic_word_token_no_longer_permits_access(raw_client):
    """A token is not accepted simply because it is not a magic word like 'invalid'."""
    with patch("httpx.post", return_value=MagicMock(status_code=401)):
        res = raw_client.get(
            "/api/v1/suppliers/SUP-00045/risk-score",
            headers={"Authorization": "Bearer non_magic_word_token"},
        )
        assert res.status_code == 401


def test_no_credentials_ever_succeed_due_to_default_settings(raw_client, monkeypatch):
    """With default settings (empty SUPPLIER_RISK_SERVICE_KEYS), no credentials succeed."""
    monkeypatch.delenv("SUPPLIER_RISK_SERVICE_KEYS", raising=False)
    monkeypatch.delenv("SUPPLIER_RISK_REQUIRE_AUTH", raising=False)

    res_missing = raw_client.get("/api/v1/suppliers/SUP-00045/risk-score")
    assert res_missing.status_code == 401

    res_service = raw_client.get(
        "/api/v1/suppliers/SUP-00045/risk-score",
        headers={"X-Caller-Service": "supplier-portal", "X-Service-Key": "valid-secret-key"},
    )
    assert res_service.status_code == 401


# ----------------------------------------------------------------------
# 7. Fix 4: Persistence, Freshness, and TTL Tests (Section C)
# ----------------------------------------------------------------------

def test_both_call_sites_call_save_assessment(client):
    """Verify that both assessment-producing call sites invoke _save_assessment."""
    # Call site 1: Sanctioned supplier
    with patch("src.analyze._save_assessment") as mock_save, \
         patch("src.analyze.fetch_risk_assessment", return_value=None):
        res = client.get("/api/v1/suppliers/SUP-00045/risk-score", headers=VALID_SERVICE_HEADERS)
        assert res.status_code == 200
        assert mock_save.called
        args, _ = mock_save.call_args
        assert args[0] == "SUP-00045"
        assert args[2].tier in ("High", "Critical")

    # Call site 2: Supplier with adverse trend headlines
    mock_headlines = {
        "Acme Risk Corp": [
            {
                "headline": "Acme Risk Corp faces massive lawsuit and strike.",
                "date": "2026-10-15",
                "score": 75.0,
            }
        ]
    }
    with patch("src.analyze._save_assessment") as mock_save2, \
         patch("src.analyze.fetch_risk_assessment", return_value=None), \
         patch("src.analyze.load_active_trend_headlines", return_value=mock_headlines):
        supplier_rec = {
            "supplier_id": "SUP-00098",
            "name": "Acme Risk Corp",
            "sanctions_flag": False,
        }
        resp = compute_canonical_supplier_risk_score(supplier_rec)
        assert mock_save2.called
        args2, _ = mock_save2.call_args
        assert args2[0] == "SUP-00098"
        assert args2[1] == "Acme Risk Corp"
        assert resp.score is not None


def test_save_assessment_exact_persisted_dictionary():
    """Verify the exact persisted dictionary structure and serialized factor/article models."""
    factor = RiskFactor(factor="strike", category="Operational", weight=25.0, description="Strike reported.")
    article = EvidenceArticle(
        headline="Workers strike",
        date="2026-10-20",
        sentiment="negative",
        score=75.0,
        signals=[EvidenceSignal(keyword="strike", weight=25.0)],
    )
    response = SupplierRiskScoreResponse(
        score=75.0,
        tier="High",
        top_factors=[factor],
        top_evidence_articles=[article],
        computed_at="2026-10-23T12:00:00Z",
    )

    with patch("src.analyze.save_risk_assessment") as mock_db_save:
        _save_assessment("SUP-00001", "Acme", response)
        assert mock_db_save.call_count == 1
        assert len(mock_db_save.call_args.args) == 1
        persisted = mock_db_save.call_args.args[0]
        assert persisted == {
            "supplier_id": "SUP-00001",
            "supplier_name": "Acme",
            "score": 75.0,
            "tier": "High",
            "top_factors": [
                {
                    "factor": "strike",
                    "category": "Operational",
                    "weight": 25.0,
                    "description": "Strike reported.",
                }
            ],
            "top_evidence_articles": [
                {
                    "headline": "Workers strike",
                    "date": "2026-10-20",
                    "sentiment": "negative",
                    "score": 75.0,
                    "signals": [{"keyword": "strike", "weight": 25.0}],
                }
            ],
            "computed_at": "2026-10-23T12:00:00Z",
        }


def test_save_risk_assessment_receives_exactly_one_dictionary_argument():
    """save_risk_assessment must receive exactly one positional dictionary argument."""
    response = SupplierRiskScoreResponse(
        score=50.0,
        tier="Low",
        top_factors=[],
        top_evidence_articles=[],
        computed_at="2026-10-23T12:00:00Z",
    )

    with patch("src.analyze.save_risk_assessment") as mock_db_save:
        _save_assessment("SUP-00002", "Test Co", response)
        assert len(mock_db_save.call_args.args) == 1
        assert isinstance(mock_db_save.call_args.args[0], dict)
        assert not mock_db_save.call_args.kwargs


def test_pymongo_error_during_persistence_logged_and_does_not_crash(client, caplog):
    """PyMongoError during save_risk_assessment is logged as a warning and does not crash score response."""
    import logging
    caplog.set_level(logging.WARNING)
    with patch("src.analyze.fetch_risk_assessment", return_value=None), \
         patch("src.analyze.save_risk_assessment", side_effect=PyMongoError("Mongo collection locked")):
        res = client.get("/api/v1/suppliers/SUP-00045/risk-score", headers=VALID_SERVICE_HEADERS)
        assert res.status_code == 200
        assert res.json()["score"] == 85.0
        assert "Could not persist risk assessment for SUP-00045" in caplog.text


def test_fresh_persisted_assessment_is_reused(client):
    """A fresh persisted assessment is reused without recomputing or persisting again."""
    fresh_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    mock_doc = {
        "supplier_id": "SUP-00045",
        "supplier_name": "TEST SANCTIONED",
        "score": 99.0,
        "tier": "Critical",
        "top_factors": [],
        "top_evidence_articles": [],
        "computed_at": fresh_time,
    }

    with patch("src.analyze.fetch_risk_assessment", return_value=mock_doc), \
         patch("src.analyze._save_assessment") as mock_save:
        res = client.get("/api/v1/suppliers/SUP-00045/risk-score", headers=VALID_SERVICE_HEADERS)
        assert res.status_code == 200
        assert res.json()["score"] == 99.0
        assert not mock_save.called


def test_stale_assessment_is_recomputed_and_saved(client):
    """A stale assessment (> TTL seconds old) is recomputed and saved."""
    stale_time = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    mock_doc = {
        "supplier_id": "SUP-00045",
        "supplier_name": "TEST SANCTIONED",
        "score": 30.0,
        "tier": "Low",
        "top_factors": [],
        "top_evidence_articles": [],
        "computed_at": stale_time,
    }

    with patch("src.analyze.fetch_risk_assessment", return_value=mock_doc), \
         patch("src.analyze._save_assessment") as mock_save:
        res = client.get("/api/v1/suppliers/SUP-00045/risk-score", headers=VALID_SERVICE_HEADERS)
        assert res.status_code == 200
        # Recomputed score for sanctioned supplier is 85.0, not the stale 30.0
        assert res.json()["score"] == 85.0
        assert mock_save.called


def test_missing_assessment_is_computed_and_saved(client):
    """When no document exists in MongoDB, the score is computed and persisted."""
    with patch("src.analyze.fetch_risk_assessment", return_value=None), \
         patch("src.analyze._save_assessment") as mock_save:
        res = client.get("/api/v1/suppliers/SUP-00045/risk-score", headers=VALID_SERVICE_HEADERS)
        assert res.status_code == 200
        assert res.json()["score"] == 85.0
        assert mock_save.called


def test_computed_risk_assessment_is_persisted_through_fake_collection(client, fake_supplier_store):
    """A computed risk assessment is actually persisted through the fake assessment collection."""
    # Ensure no pre-existing assessment for SUP-00045
    fake_supplier_store.assessments.delete_many({"supplier_id": "SUP-00045"})
    assert fake_supplier_store.assessments.find_one({"supplier_id": "SUP-00045"}) is None

    res = client.get("/api/v1/suppliers/SUP-00045/risk-score")
    assert res.status_code == 200
    assert res.json()["score"] == 85.0

    # Verify persisted document in fake assessment collection
    saved = fake_supplier_store.assessments.find_one({"supplier_id": "SUP-00045"})
    assert saved is not None
    assert saved["supplier_id"] == "SUP-00045"
    assert saved["score"] == 85.0
    assert saved["tier"] in ("Critical", "High")
    assert "updated_at" in saved


def test_stale_saved_assessment_is_recomputed_rather_than_returned(client, fake_supplier_store):
    """A stale saved assessment is recomputed rather than returned."""
    stale_time = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_doc = {
        "supplier_id": "SUP-00045",
        "supplier_name": "TEST UN ENTITY 01",
        "score": 15.0,
        "tier": "Low",
        "top_factors": [],
        "top_evidence_articles": [],
        "computed_at": stale_time,
    }
    fake_supplier_store.assessments.delete_many({"supplier_id": "SUP-00045"})
    fake_supplier_store.assessments.insert_one(stale_doc)

    res = client.get("/api/v1/suppliers/SUP-00045/risk-score")
    assert res.status_code == 200
    data = res.json()
    # Recomputed score for sanctioned SUP-00045 is 85.0, not stale 15.0
    assert data["score"] == 85.0
    assert data["tier"] in ("Critical", "High")

    # Document in fake collection must have been updated with recomputed score
    updated = fake_supplier_store.assessments.find_one({"supplier_id": "SUP-00045"})
    assert updated is not None
    assert updated["score"] == 85.0



def test_invalid_or_missing_computed_at_not_fresh():
    """Missing, invalid, and malformed computed_at values are safely deemed not fresh."""
    assert not _is_fresh(None)
    assert not _is_fresh("")
    assert not _is_fresh("   ")
    assert not _is_fresh("not-a-datetime")
    assert not _is_fresh(123456)
    assert not _is_fresh({"date": "now"})
    assert not _is_fresh("9999-99-99T99:99:99Z")

    # Timezone-naive datetime handled safely without raising TypeError
    now_utc = datetime.now(timezone.utc)
    fresh_naive_str = (now_utc - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    assert _is_fresh(fresh_naive_str)

    stale_naive_str = (now_utc - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
    assert not _is_fresh(stale_naive_str)


def test_ttl_configuration_defaults_and_respects_overrides():
    """TTL configuration defaults to 3600 seconds and respects overrides."""
    assert RISK_ASSESSMENT_TTL_SECONDS == 3600
    assert get_risk_assessment_ttl_seconds() == 3600
    assert get_settings().risk_assessment_ttl_seconds == 3600

    now_utc = datetime.now(timezone.utc)
    ts_2000s_old = (now_utc - timedelta(seconds=2000)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Under default 3600s TTL, 2000s is fresh
    assert _is_fresh(ts_2000s_old)

    # With override to 1800s, 2000s is stale
    with patch.dict(os.environ, {"RISK_ASSESSMENT_TTL_SECONDS": "1800"}):
        assert get_risk_assessment_ttl_seconds() == 1800
        assert not _is_fresh(ts_2000s_old)
        # Explicit override parameter also respected
        assert _is_fresh(ts_2000s_old, ttl_seconds=3600)


# ----------------------------------------------------------------------
# 9. Fix 6: Evidence Integrity & Sanction Mapping Tests
# ----------------------------------------------------------------------

def test_evidence_article_optional_date():
    """EvidenceArticle model supports optional date defaulting to None."""
    article = EvidenceArticle(
        headline="Test headline",
        sentiment="negative",
        score=50.0,
    )
    assert article.date is None
    dumped = article.model_dump()
    assert dumped["date"] is None


def test_missing_evidence_date_serializes_as_null(client):
    """Missing evidence date serializes as null, never fabricated as today's date."""
    mock_trend_result = {
        "current_risk_score": 60.0,
        "current_risk_tier": "Medium",
        "top_evidence": [
            {
                "headline": "Acme Corp suffers sudden disruption and strike.",
                "sentiment": "negative",
                "score": 60.0,
                "signals": [{"keyword": "strike", "weight": 25.0}],
                # date is deliberately missing
            }
        ],
    }
    with patch("src.analyze.fetch_risk_assessment", return_value=None), \
         patch("src.analyze.load_active_trend_headlines", return_value={"Acme Corp": [{"date": "2026-03-01", "headline": "strike"}]}), \
         patch("src.analyze.calculate_supplier_trend", return_value=mock_trend_result):
        supplier_rec = {
            "supplier_id": "SUP-00001",
            "name": "Acme Corp",
            "sanctions_flag": False,
        }
        res = compute_canonical_supplier_risk_score(supplier_rec)
        assert len(res.top_evidence_articles) > 0
        ev = res.top_evidence_articles[0]
        assert ev.date is None

        # Verify JSON serialization through model_dump
        dumped = res.model_dump()
        assert dumped["top_evidence_articles"][0]["date"] is None
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert dumped["top_evidence_articles"][0]["date"] != today_str


def test_existing_evidence_date_preserved():
    """Existing evidence with a real source date preserves that exact date."""
    mock_headlines = {
        "Acme Corp": [
            {
                "headline": "Acme Corp reports major product recall.",
                "date": "2026-02-14",
                "score": 70.0,
            }
        ]
    }
    with patch("src.analyze.fetch_risk_assessment", return_value=None), \
         patch("src.analyze.load_active_trend_headlines", return_value=mock_headlines):
        supplier_rec = {
            "supplier_id": "SUP-00001",
            "name": "Acme Corp",
            "sanctions_flag": False,
        }
        res = compute_canonical_supplier_risk_score(supplier_rec)
        assert len(res.top_evidence_articles) > 0
        ev = res.top_evidence_articles[0]
        assert ev.date == "2026-02-14"


def test_sanction_signals_use_security_category():
    """Sanction keywords and master designations map to Security category, not Legal."""
    assert SIGNAL_CATEGORIES["sanction"] == "Security"

    # In trend calculation with a sanction headline
    mock_headlines = {
        "Sanctioned Partner": [
            {
                "headline": "Sanctioned Partner faces international sanction and export ban.",
                "date": "2026-03-01",
                "score": 85.0,
            }
        ]
    }
    with patch("src.analyze.fetch_risk_assessment", return_value=None), \
         patch("src.analyze.load_active_trend_headlines", return_value=mock_headlines):
        supplier_rec = {
            "supplier_id": "SUP-00010",
            "name": "Sanctioned Partner",
            "sanctions_flag": False,
        }
        res = compute_canonical_supplier_risk_score(supplier_rec)
        sanction_factors = [f for f in res.top_factors if f.factor == "sanction"]
        assert len(sanction_factors) > 0
        assert sanction_factors[0].category == "Security"


def test_validate_risk_assessment_ttl_seconds_accepts_positive_integers():
    """validate_risk_assessment_ttl_seconds accepts positive integers and string representations."""
    assert validate_risk_assessment_ttl_seconds(3600) == 3600
    assert validate_risk_assessment_ttl_seconds("1800") == 1800
    assert validate_risk_assessment_ttl_seconds(1) == 1
    assert validate_risk_assessment_ttl_seconds(60.0) == 60


@pytest.mark.parametrize("invalid_val", [0, -1, -3600, "0", "-60", "abc", 12.5, None, True, False])
def test_validate_risk_assessment_ttl_seconds_rejects_invalid_or_non_positive(invalid_val):
    """validate_risk_assessment_ttl_seconds raises ValueError or TypeError for invalid/non-positive values."""
    with pytest.raises((ValueError, TypeError)):
        validate_risk_assessment_ttl_seconds(invalid_val)


def test_settings_raises_value_error_on_invalid_ttl():
    """Settings raises ValueError when initialized with non-positive or invalid TTL."""
    with pytest.raises(ValueError, match="risk_assessment_ttl_seconds must be >= 1"):
        Settings(risk_assessment_ttl_seconds=0)

    with pytest.raises(ValueError, match="risk_assessment_ttl_seconds must be >= 1"):
        Settings(risk_assessment_ttl_seconds=-100)

    with patch.dict(os.environ, {"RISK_ASSESSMENT_TTL_SECONDS": "-500"}):
        with pytest.raises(ValueError, match="risk_assessment_ttl_seconds must be >= 1"):
            Settings()

    with patch.dict(os.environ, {"RISK_ASSESSMENT_TTL_SECONDS": "not-an-int"}):
        with pytest.raises(ValueError, match="risk_assessment_ttl_seconds must be a positive integer"):
            Settings()


def test_get_risk_assessment_ttl_seconds_falls_back_on_invalid_env():
    """get_risk_assessment_ttl_seconds safely ignores non-positive or invalid env values."""
    with patch.dict(os.environ, {"RISK_ASSESSMENT_TTL_SECONDS": "7200"}):
        assert get_risk_assessment_ttl_seconds() == 7200

    with patch.dict(os.environ, {"RISK_ASSESSMENT_TTL_SECONDS": "-10"}):
        # Falls back to Settings or RISK_ASSESSMENT_TTL_SECONDS default
        assert get_risk_assessment_ttl_seconds() > 0

    with patch.dict(os.environ, {"RISK_ASSESSMENT_TTL_SECONDS": "invalid"}):
        assert get_risk_assessment_ttl_seconds() > 0
