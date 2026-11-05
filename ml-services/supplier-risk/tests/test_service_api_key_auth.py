"""
Unit tests for Supplier Risk Service API Key Authentication (Round 15 Milestone 5).

Verifies:
1. Valid API key:
   - Mock Platform /service-verify returning HTTP 200.
   - Supplier Risk accepts the request (HTTP 200) with populated response.
2. Missing or empty API key:
   - Platform is not called.
   - Supplier Risk responds HTTP 401.
   - No risk-score business processing (supplier lookup or score computation) occurs.
3. Revoked / Invalid API key:
   - Mock Platform /service-verify returning HTTP 401.
   - Supplier Risk responds HTTP 401.
   - No risk-score business processing occurs.
4. Platform unavailable / timeouts:
   - Platform timeout (httpx.TimeoutException) returns HTTP 503.
   - Platform connection error (httpx.ConnectError) returns HTTP 503.
   - Platform unexpected error response (HTTP 500, 502, 503) fails closed with HTTP 503.
   - Access is not allowed.
5. Existing user JWT authentication through Platform /api/v1/auth/verify continues passing.
6. Secrets are never exposed in error responses or logs.
7. Protected endpoint /seed-mappings also authenticates with service API key.
"""

from unittest.mock import MagicMock, patch
import httpx
import pytest
from fastapi.testclient import TestClient

from src.analyze import app, require_caller


@pytest.fixture
def raw_client():
    """Raw client that does not override require_caller, exercising real authentication."""
    class RawTestClient(TestClient):
        def request(self, *args, **kwargs):
            saved = app.dependency_overrides.pop(require_caller, None)
            try:
                return super().request(*args, **kwargs)
            finally:
                if saved is not None:
                    app.dependency_overrides[require_caller] = saved

    with RawTestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def mock_sentiment():
    """Mock FinBERT sentiment inference to keep tests fast and deterministic."""
    with patch("src.predict.analyze_sentiment") as mock_sa, \
         patch("src.analyze.init_model") as mock_im:
        mock_sa.return_value = {"label": "neutral", "confidence": 0.99}
        yield mock_sa, mock_im


# ===========================================================================
# 1. Valid Service API Key (HTTP 200)
# ===========================================================================

def test_valid_service_api_key_accepted_200(raw_client):
    """
    Valid service API key verified by Platform /service-verify returning HTTP 200
    allows the request and completes risk-score processing.
    """
    mock_platform_resp = MagicMock(status_code=200)
    mock_platform_resp.json.return_value = {
        "authenticated": True,
        "service": "supplier-portal",
        "auth_type": "api_key",
    }

    mock_supplier_doc = {
        "supplier_id": "SUP-00045",
        "name": "Acme Supplier Inc",
        "sanctions_flag": False,
    }

    with patch("httpx.post", return_value=mock_platform_resp) as mock_post, \
         patch("src.analyze.resolve_canonical_supplier", return_value=mock_supplier_doc) as mock_resolve, \
         patch("src.analyze.fetch_risk_assessment", return_value=None), \
         patch("src.analyze.load_active_trend_headlines", return_value={}):

        response = raw_client.get(
            "/api/v1/suppliers/SUP-00045/risk-score",
            headers={"X-API-Key": "sk_test_valid_gateway_key_12345"},
        )

        assert response.status_code == 200
        mock_post.assert_called_once()

        # Check call arguments to Platform /service-verify
        call_args, call_kwargs = mock_post.call_args
        verify_url = call_args[0]
        assert verify_url.endswith("/api/v1/auth/service-verify")
        assert call_kwargs["headers"]["X-API-Key"] == "sk_test_valid_gateway_key_12345"

        # Supplier resolution was performed
        assert mock_resolve.called

        data = response.json()
        assert data["supplier_id"] == "SUP-00045"


# ===========================================================================
# 2. Missing or Empty API Key (HTTP 401 & No Business Processing)
# ===========================================================================

def test_missing_api_key_returns_401_without_calling_platform_or_business_logic(raw_client):
    """
    Missing X-API-Key (and missing credentials) returns HTTP 401 without
    calling Platform or executing any database/supplier risk logic.
    """
    with patch("httpx.post") as mock_post, \
         patch("src.analyze.resolve_canonical_supplier") as mock_resolve, \
         patch("src.analyze.compute_canonical_supplier_risk_score") as mock_compute:

        response = raw_client.get("/api/v1/suppliers/SUP-00045/risk-score")

        assert response.status_code == 401
        assert response.json()["error_code"] == "UNAUTHORIZED"

        # Platform verification must NOT be called
        assert not mock_post.called

        # Business processing must NOT occur
        assert not mock_resolve.called
        assert not mock_compute.called


def test_empty_api_key_returns_401_without_calling_platform_or_business_logic(raw_client):
    """
    Empty or whitespace X-API-Key returns HTTP 401 without calling Platform
    or executing any business logic.
    """
    for empty_val in ["", "   "]:
        with patch("httpx.post") as mock_post, \
             patch("src.analyze.resolve_canonical_supplier") as mock_resolve, \
             patch("src.analyze.compute_canonical_supplier_risk_score") as mock_compute:

            response = raw_client.get(
                "/api/v1/suppliers/SUP-00045/risk-score",
                headers={"X-API-Key": empty_val},
            )

            assert response.status_code == 401
            assert response.json()["error_code"] == "UNAUTHORIZED"
            assert not mock_post.called
            assert not mock_resolve.called
            assert not mock_compute.called


# ===========================================================================
# 3. Revoked / Invalid API Key (HTTP 401 & No Business Processing)
# ===========================================================================

def test_revoked_api_key_returns_401_without_business_processing(raw_client):
    """
    Platform /service-verify returning HTTP 401 (e.g. revoked key) results in
    Supplier Risk returning HTTP 401 without business processing.
    """
    mock_platform_resp = MagicMock(status_code=401)
    mock_platform_resp.json.return_value = {"detail": "Service API key is inactive or revoked"}

    with patch("httpx.post", return_value=mock_platform_resp) as mock_post, \
         patch("src.analyze.resolve_canonical_supplier") as mock_resolve, \
         patch("src.analyze.compute_canonical_supplier_risk_score") as mock_compute:

        response = raw_client.get(
            "/api/v1/suppliers/SUP-00045/risk-score",
            headers={"X-API-Key": "sk_test_revoked_key_99999"},
        )

        assert response.status_code == 401
        assert response.json()["error_code"] == "UNAUTHORIZED"
        mock_post.assert_called_once()

        # No business processing on revoked keys
        assert not mock_resolve.called
        assert not mock_compute.called


def test_platform_authenticated_false_returns_401(raw_client):
    """
    If Platform returns 200 OK but body specifies authenticated=False,
    Supplier Risk rejects the request with HTTP 401.
    """
    mock_platform_resp = MagicMock(status_code=200)
    mock_platform_resp.json.return_value = {"authenticated": False}

    with patch("httpx.post", return_value=mock_platform_resp), \
         patch("src.analyze.resolve_canonical_supplier") as mock_resolve:

        response = raw_client.get(
            "/api/v1/suppliers/SUP-00045/risk-score",
            headers={"X-API-Key": "sk_unauthenticated_key"},
        )

        assert response.status_code == 401
        assert not mock_resolve.called


# ===========================================================================
# 4. Platform Unavailable / Timeout (HTTP 503 Fail-Closed)
# ===========================================================================

def test_platform_timeout_returns_503_fail_closed(raw_client):
    """
    When Platform /service-verify times out, Supplier Risk fails closed with HTTP 503.
    """
    with patch("httpx.post", side_effect=httpx.TimeoutException("Platform timeout")), \
         patch("src.analyze.resolve_canonical_supplier") as mock_resolve:

        response = raw_client.get(
            "/api/v1/suppliers/SUP-00045/risk-score",
            headers={"X-API-Key": "sk_test_key_timeout"},
        )

        assert response.status_code == 503
        assert response.json()["error_code"] == "RISK_UNAVAILABLE"
        assert not mock_resolve.called


def test_platform_connection_error_returns_503_fail_closed(raw_client):
    """
    When Platform /service-verify has network connection failure, Supplier Risk fails closed with 503.
    """
    with patch("httpx.post", side_effect=httpx.ConnectError("Platform unreachable")), \
         patch("src.analyze.resolve_canonical_supplier") as mock_resolve:

        response = raw_client.get(
            "/api/v1/suppliers/SUP-00045/risk-score",
            headers={"X-API-Key": "sk_test_key_connect_error"},
        )

        assert response.status_code == 503
        assert response.json()["error_code"] == "RISK_UNAVAILABLE"
        assert not mock_resolve.called


def test_platform_unexpected_500_response_fails_closed_with_503(raw_client):
    """
    When Platform /service-verify returns unexpected 500 status code, Supplier Risk fails closed with 503.
    """
    mock_platform_resp = MagicMock(status_code=500)
    with patch("httpx.post", return_value=mock_platform_resp), \
         patch("src.analyze.resolve_canonical_supplier") as mock_resolve:

        response = raw_client.get(
            "/api/v1/suppliers/SUP-00045/risk-score",
            headers={"X-API-Key": "sk_test_key_server_error"},
        )

        assert response.status_code == 503
        assert response.json()["error_code"] == "RISK_UNAVAILABLE"
        assert not mock_resolve.called


# ===========================================================================
# 5. Existing User JWT Authentication Continues Passing
# ===========================================================================

def test_existing_jwt_authentication_continues_passing(raw_client):
    """
    User JWT authentication via Authorization: Bearer <token> verified by
    Platform /api/v1/auth/verify continues to work seamlessly alongside service API keys.
    """
    mock_verify_resp = MagicMock(status_code=200)
    mock_verify_resp.json.return_value = {
        "valid": True,
        "email": "analyst@company.com",
        "role": "analyst",
    }

    mock_supplier_doc = {
        "supplier_id": "SUP-00045",
        "name": "Acme Supplier Inc",
        "sanctions_flag": False,
    }

    with patch("httpx.post", return_value=mock_verify_resp) as mock_post, \
         patch("src.analyze.resolve_canonical_supplier", return_value=mock_supplier_doc), \
         patch("src.analyze.fetch_risk_assessment", return_value=None), \
         patch("src.analyze.load_active_trend_headlines", return_value={}):

        response = raw_client.get(
            "/api/v1/suppliers/SUP-00045/risk-score",
            headers={"Authorization": "Bearer valid.user.jwt.token"},
        )

        assert response.status_code == 200
        mock_post.assert_called_once()
        verify_url = mock_post.call_args[0][0]
        assert verify_url.endswith("/api/v1/auth/verify")


# ===========================================================================
# 6. Protected Endpoint /seed-mappings Authentication
# ===========================================================================

def test_seed_mappings_authenticates_with_service_api_key(raw_client):
    """
    POST /seed-mappings accepts a valid service API key.
    """
    mock_platform_resp = MagicMock(status_code=200)
    mock_platform_resp.json.return_value = {
        "authenticated": True,
        "service": "supplier-portal",
    }

    with patch("httpx.post", return_value=mock_platform_resp), \
         patch("src.analyze.seed_supplier_mappings", return_value={"inserted": 5, "updated": 0}):

        response = raw_client.post(
            "/api/v1/supplier-risk/seed-mappings",
            headers={"X-API-Key": "sk_test_seed_admin_key"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_seed_mappings_rejects_missing_or_invalid_service_api_key(raw_client):
    """
    POST /seed-mappings rejects missing or invalid service API key with 401.
    """
    # Missing key
    res_missing = raw_client.post("/api/v1/supplier-risk/seed-mappings")
    assert res_missing.status_code == 401

    # Revoked key
    mock_platform_resp = MagicMock(status_code=401)
    with patch("httpx.post", return_value=mock_platform_resp):
        res_invalid = raw_client.post(
            "/api/v1/supplier-risk/seed-mappings",
            headers={"X-API-Key": "sk_test_revoked_seed_key"},
        )
        assert res_invalid.status_code == 401


# ===========================================================================
# 7. No Secret Leaked in Response or Error Message
# ===========================================================================

def test_secret_never_exposed_in_error_responses(raw_client):
    """
    Verify that rejected requests never echo or leak the secret API key in responses.
    """
    secret = "sk_sensitive_secret_do_not_leak_456"
    mock_platform_resp = MagicMock(status_code=401)

    with patch("httpx.post", return_value=mock_platform_resp):
        response = raw_client.get(
            "/api/v1/suppliers/SUP-00045/risk-score",
            headers={"X-API-Key": secret},
        )

        assert response.status_code == 401
        assert secret not in response.text


def _platform_resp(status_code, body):
    resp = MagicMock(status_code=status_code)
    resp.json.return_value = body
    return resp


GATEWAY_OK = {
    "authenticated": True,
    "service": "gateway-bff",
    "auth_type": "api_key",
}

SUPPLIER_DOC = {
    "supplier_id": "SUP-00045",
    "name": "Acme Supplier Inc",
    "sanctions_flag": False,
}


def test_gateway_key_without_user_jwt_returns_401(raw_client):
    """The gateway's key alone is not enough: an anonymous request through the gateway gets 401."""
    with patch("httpx.post", return_value=_platform_resp(200, GATEWAY_OK)), \
         patch("src.analyze.resolve_canonical_supplier") as mock_resolve:
        response = raw_client.get(
            "/api/v1/suppliers/SUP-00045/risk-score",
            headers={
                "X-API-Key": "sk_test_gateway_key",
                "X-Caller-Service": "api-gateway",
            },
        )

    assert response.status_code == 401
    assert not mock_resolve.called


def test_gateway_key_with_valid_user_jwt_returns_200(raw_client):
    """Through the gateway, both the gateway key and the user's JWT are verified."""
    user_ok = _platform_resp(
        200,
        {
            "valid": True,
            "email": "analyst@company.com",
            "role": "analyst",
        },
    )

    with patch(
        "httpx.post",
        side_effect=[
            _platform_resp(200, GATEWAY_OK),
            user_ok,
        ],
    ) as mock_post, \
         patch(
             "src.analyze.resolve_canonical_supplier",
             return_value=SUPPLIER_DOC,
         ), \
         patch("src.analyze.fetch_risk_assessment", return_value=None), \
         patch("src.analyze.load_active_trend_headlines", return_value={}):
        response = raw_client.get(
            "/api/v1/suppliers/SUP-00045/risk-score",
            headers={
                "X-API-Key": "sk_test_gateway_key",
                "X-Caller-Service": "api-gateway",
                "Authorization": "Bearer valid.user.jwt.token",
            },
        )

    assert response.status_code == 200
    urls = [call.args[0] for call in mock_post.call_args_list]
    assert urls[0].endswith("/api/v1/auth/service-verify")
    assert urls[1].endswith("/api/v1/auth/verify")


def test_service_not_in_allowlist_returns_403(raw_client):
    """A valid key from a service that is not an allowed caller gets 403, and nothing runs."""
    inventory_ok = _platform_resp(
        200,
        {
            "authenticated": True,
            "service": "inventory",
            "auth_type": "api_key",
        },
    )

    with patch("httpx.post", return_value=inventory_ok), \
         patch("src.analyze.seed_supplier_mappings") as mock_seed:
        response = raw_client.post(
            "/api/v1/supplier-risk/seed-mappings",
            headers={"X-API-Key": "sk_test_inventory_key"},
        )

    assert response.status_code == 403
    assert response.json()["error_code"] == "FORBIDDEN"
    assert not mock_seed.called


def test_platform_200_without_authenticated_true_returns_401(raw_client):
    """A 200 from Platform only counts when it says authenticated: true."""
    with patch("httpx.post", return_value=_platform_resp(200, {})), \
         patch("src.analyze.resolve_canonical_supplier") as mock_resolve:
        response = raw_client.get(
            "/api/v1/suppliers/SUP-00045/risk-score",
            headers={"X-API-Key": "sk_test_some_key"},
        )

    assert response.status_code == 401
    assert not mock_resolve.called
