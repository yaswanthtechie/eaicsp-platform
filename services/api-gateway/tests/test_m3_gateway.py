"""
Milestone 3 (M3) Test Suite — API Gateway Rate Limiting & Resilience.

Verifies:
1. Health endpoint bypasses rate limiting (never 429).
2. Repeated health calls do not consume user or IP rate-limit quota.
3. Normal routes remain rate limited when quota is exceeded.
4. Route-specific rate limits are enforced.
5. Authenticated user route limit with per-user isolation.
6. Role-based limits remain compatible on normal routes.
7. Anonymous / IP fallback remains compatible on both normal and route-limited endpoints.
8. Health endpoint bypass works even after client quota is completely exhausted.
9. Aggregation partial response when one downstream service fails (graceful degradation).
10. Aggregation partial response when multiple downstream services fail.
11. Aggregation unavailable response when all downstream services fail (no exception leaks).
12. Strict health path matching (arbitrary paths with 'health' substring are NOT exempt).
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.middleware.rate_limit import in_memory_limiter
from app.middleware.ratelimit import limiter

try:
    import jwt
except ImportError:
    jwt = None


def create_token(user_id: str | None = None, role: str | None = None) -> str:
    """Generate a JWT bearer token for testing."""
    payload = {}
    if user_id is not None:
        payload["user_id"] = user_id
    if role is not None:
        payload["role"] = role

    if jwt is not None:
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    import base64
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{header}.{body}.mock_signature"


@pytest.fixture(autouse=True)
def reset_m3_state():
    """Reset rate limiter and settings state between tests."""
    in_memory_limiter.reset()
    limiter.enabled = True

    old_route_limits = dict(settings.ROUTE_RATE_LIMITS)
    old_load_test = getattr(settings, "LOAD_TEST_MODE", False)
    settings.LOAD_TEST_MODE = False

    yield

    in_memory_limiter.reset()
    settings.ROUTE_RATE_LIMITS = old_route_limits
    settings.LOAD_TEST_MODE = old_load_test


@pytest.fixture
def client():
    """Create a FastAPI test client."""
    with TestClient(app) as test_client:
        yield test_client


# ===========================================================================
# 1. Health Endpoint Bypasses Rate Limiting
# ===========================================================================

@patch("app.services.health.httpx.AsyncClient.get", new_callable=AsyncMock)
def test_m3_1_health_endpoint_bypasses_rate_limiting(mock_get, client):
    """
    M3 Requirement 1:
    GET /health must NEVER be rate limited (never returns 429),
    even when hit with a burst of requests exceeding normal and SlowAPI limits.
    """
    mock_get.return_value = httpx.Response(
        status_code=200,
        request=httpx.Request("GET", "http://test"),
    )

    # Send 120 requests to /health (exceeding SlowAPI 100/min and default 60/min)
    for i in range(120):
        response = client.get("/health")
        assert response.status_code == 200, f"Request {i} failed with status {response.status_code}"


# ===========================================================================
# 2. Repeated Health Calls Do Not Consume Quota
# ===========================================================================

@patch("app.services.health.httpx.AsyncClient.get", new_callable=AsyncMock)
def test_m3_2_repeated_health_calls_do_not_consume_quota(mock_get, client):
    """
    M3 Requirement 2:
    Repeated /health requests must NOT consume tokens from the user/IP bucket.
    After 50 /health requests, a client must still have full quota on normal routes.
    """
    mock_get.return_value = httpx.Response(
        status_code=200,
        request=httpx.Request("GET", "http://test"),
    )

    token = create_token(user_id="analyst_m3", role="analyst")
    headers = {"Authorization": f"Bearer {token}"}
    analyst_quota = settings.get_role_rate_limit("analyst")  # 60

    # Step 1: Send 50 requests to /health
    for _ in range(50):
        res = client.get("/health", headers=headers)
        assert res.status_code == 200

    # Step 2: Client should still have full quota (60) on normal route "/"
    for i in range(analyst_quota):
        res = client.get("/", headers=headers)
        assert res.status_code == 200, f"Request {i} unexpectedly rate limited"

    # Request 61 on normal route exceeds quota
    res_over = client.get("/", headers=headers)
    assert res_over.status_code == 429


# ===========================================================================
# 3. Normal Route Still Gets Rate Limited
# ===========================================================================

def test_m3_3_normal_route_still_gets_rate_limited(client):
    """
    M3 Requirement 3:
    Normal routes remain strictly rate limited according to configured quotas.
    Exceeding the quota returns HTTP 429 with correct headers.
    """
    default_limit = settings.get_role_rate_limit("default")  # 60

    for i in range(default_limit):
        res = client.get("/")
        assert res.status_code == 200, f"Request {i} failed unexpectedly"

    res_blocked = client.get("/")
    assert res_blocked.status_code == 429
    assert res_blocked.json()["detail"] == "Too Many Requests"
    assert res_blocked.headers["X-RateLimit-Limit"] == str(default_limit)
    assert res_blocked.headers["X-RateLimit-Remaining"] == "0"
    assert "Retry-After" in res_blocked.headers


# ===========================================================================
# 4. Route-Specific Limit Applied
# ===========================================================================

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_m3_4_route_specific_limit_applied(mock_send, client):
    """
    M3 Requirement 4:
    A route with a specific configured limit (e.g. 5 req/min) enforces that limit.
    """
    settings.ROUTE_RATE_LIMITS["/api/v1/auth"] = 5

    mock_send.return_value = httpx.Response(
        status_code=200,
        content=b'{"status":"ok"}',
        request=httpx.Request("GET", "http://test/api/v1/auth/verify"),
    )

    # 5 requests allowed
    for i in range(5):
        res = client.get("/api/v1/auth/verify")
        assert res.status_code == 200
        assert res.headers["X-RateLimit-Limit"] == "5"

    # 6th request rejected with 429
    res_over = client.get("/api/v1/auth/verify")
    assert res_over.status_code == 429
    assert res_over.headers["X-RateLimit-Limit"] == "5"
    assert res_over.headers["X-RateLimit-Remaining"] == "0"


# ===========================================================================
# 5. Authenticated User Route Limit
# ===========================================================================

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_m3_5_authenticated_user_route_limit(mock_send, client):
    """
    M3 Requirement 5:
    Authenticated users on route-limited endpoints are isolated per user identity
    (user:<user_id>:<route>), and their route-specific bucket does not exhaust
    their normal route quota.
    """
    settings.ROUTE_RATE_LIMITS["/api/v1/auth"] = 3

    mock_send.return_value = httpx.Response(
        status_code=200,
        content=b'{"status":"ok"}',
        request=httpx.Request("GET", "http://test/api/v1/auth/verify"),
    )

    token_a = create_token(user_id="user_alpha", role="analyst")
    token_b = create_token(user_id="user_beta", role="analyst")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A exhausts their route limit on /api/v1/auth (3 reqs)
    for _ in range(3):
        res = client.get("/api/v1/auth/verify", headers=headers_a)
        assert res.status_code == 200

    res_a_over = client.get("/api/v1/auth/verify", headers=headers_a)
    assert res_a_over.status_code == 429

    # User B is NOT blocked on /api/v1/auth
    res_b = client.get("/api/v1/auth/verify", headers=headers_b)
    assert res_b.status_code == 200

    # User A is NOT blocked on normal route "/" (independent quota)
    res_a_normal = client.get("/", headers=headers_a)
    assert res_a_normal.status_code == 200


# ===========================================================================
# 6. Role Limit Remains Compatible
# ===========================================================================

def test_m3_6_role_limit_remains_compatible(client):
    """
    M3 Requirement 6:
    Role-based quotas on normal routes remain 100% compatible.
    CEO: 200, VP: 200, Procurement: 100, Analyst: 60.
    """
    ceo_token = create_token(user_id="c1", role="ceo")
    vp_token = create_token(user_id="v1", role="vp_operations")
    proc_token = create_token(user_id="p1", role="procurement_manager")
    analyst_token = create_token(user_id="a1", role="analyst")

    res_ceo = client.get("/", headers={"Authorization": f"Bearer {ceo_token}"})
    assert res_ceo.headers["X-RateLimit-Limit"] == "200"

    res_vp = client.get("/", headers={"Authorization": f"Bearer {vp_token}"})
    assert res_vp.headers["X-RateLimit-Limit"] == "200"

    res_proc = client.get("/", headers={"Authorization": f"Bearer {proc_token}"})
    assert res_proc.headers["X-RateLimit-Limit"] == "100"

    res_analyst = client.get("/", headers={"Authorization": f"Bearer {analyst_token}"})
    assert res_analyst.headers["X-RateLimit-Limit"] == "60"


# ===========================================================================
# 7. Anonymous / IP Fallback Remains Compatible
# ===========================================================================

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_m3_7_anonymous_ip_fallback_remains_compatible(mock_send, client):
    """
    M3 Requirement 7:
    Anonymous requests fall back to client IP for both normal routes (default quota)
    and route-specific routes (route quota).
    """
    settings.ROUTE_RATE_LIMITS["/api/v1/auth"] = 10

    mock_send.return_value = httpx.Response(
        status_code=200,
        content=b'{"status":"ok"}',
        request=httpx.Request("GET", "http://test/api/v1/auth/ping"),
    )

    # Normal route uses default 60
    res_normal = client.get("/")
    assert res_normal.headers["X-RateLimit-Limit"] == "60"

    # Route-specific route uses route limit 10
    res_route = client.get("/api/v1/auth/ping")
    assert res_route.headers["X-RateLimit-Limit"] == "10"


# ===========================================================================
# 8. Health Bypass Works Even After Quota Exhaustion
# ===========================================================================

@patch("app.services.health.httpx.AsyncClient.get", new_callable=AsyncMock)
def test_m3_8_health_bypass_works_even_after_quota_exhaustion(mock_get, client):
    """
    M3 Requirement 8:
    When a client exhausts their rate limit on normal routes and receives 429,
    GET /health still succeeds with 200 OK.
    """
    mock_get.return_value = httpx.Response(
        status_code=200,
        request=httpx.Request("GET", "http://test"),
    )

    token = create_token(user_id="exhausted_user", role="analyst")
    headers = {"Authorization": f"Bearer {token}"}
    limit = settings.get_role_rate_limit("analyst")

    # Exhaust quota
    for _ in range(limit):
        res = client.get("/", headers=headers)
        assert res.status_code == 200

    # Verify normal route is now blocked
    blocked = client.get("/", headers=headers)
    assert blocked.status_code == 429

    # /health must still succeed!
    health_res = client.get("/health", headers=headers)
    assert health_res.status_code == 200

    # Normal route remains blocked
    blocked_again = client.get("/", headers=headers)
    assert blocked_again.status_code == 429


# ===========================================================================
# 9. Aggregation Graceful Degradation (One Downstream Fails -> Partial)
# ===========================================================================

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_m3_9_aggregation_partial_when_one_fails(mock_send, client):
    """
    M3 Requirement 9:
    When one downstream service fails (e.g. Compliance returns 500),
    dashboard aggregation returns HTTP 200 with status: partial.
    """
    async def side_effect(request: httpx.Request, *args, **kwargs):
        url = str(request.url)
        if "/api/v1/inventory" in url:
            return httpx.Response(200, json=[{"item": "SKU-01"}], request=request)
        if "/api/v1/compliance" in url:
            return httpx.Response(500, json={"error": "db failure"}, request=request)
        if "/api/v1/shipments" in url:
            return httpx.Response(200, json=[{"shipment": "S-01"}], request=request)
        return httpx.Response(404, request=request)

    mock_send.side_effect = side_effect

    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200

    data = res.json()
    assert data["status"] == "partial"
    assert data["inventory"]["status"] == "ok"
    assert data["compliance"]["status"] == "unavailable"
    assert data["logistics"]["status"] == "ok"


# ===========================================================================
# 10. Aggregation Graceful Degradation (Multiple / All Fail)
# ===========================================================================

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_m3_10_aggregation_partial_when_two_fail(mock_send, client):
    """
    M3 Requirement 10 (Multiple Failures):
    When two services fail (e.g. Inventory connection error, Logistics timeout),
    dashboard aggregation returns HTTP 200 with status: partial.
    """
    async def side_effect(request: httpx.Request, *args, **kwargs):
        url = str(request.url)
        if "/api/v1/inventory" in url:
            raise httpx.ConnectError("Connection refused", request=request)
        if "/api/v1/compliance" in url:
            return httpx.Response(200, json={"audits": "ok"}, request=request)
        if "/api/v1/shipments" in url:
            raise httpx.TimeoutException("Timeout", request=request)
        return httpx.Response(404, request=request)

    mock_send.side_effect = side_effect

    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200

    data = res.json()
    assert data["status"] == "partial"
    assert data["inventory"]["status"] == "unavailable"
    assert data["compliance"]["status"] == "ok"
    assert data["logistics"]["status"] == "unavailable"


@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_m3_11_aggregation_unavailable_when_all_fail(mock_send, client):
    """
    M3 Requirement 10 (All Failures):
    When all three downstreams fail, dashboard aggregation returns HTTP 200
    with status: unavailable, and no exceptions leak to the caller.
    """
    async def side_effect(request: httpx.Request, *args, **kwargs):
        raise httpx.ConnectError("All downstreams offline", request=request)

    mock_send.side_effect = side_effect

    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200

    data = res.json()
    assert data["status"] == "unavailable"
    assert data["inventory"]["status"] == "unavailable"
    assert data["compliance"]["status"] == "unavailable"
    assert data["logistics"]["status"] == "unavailable"


# ===========================================================================
# 12. Strict Health Path Specificity
# ===========================================================================

def test_m3_12_arbitrary_health_paths_not_exempt():
    """
    Verify that arbitrary paths containing 'health' (e.g. /healthy, /api/v1/health-insurance)
    are NOT recognized as registered health checks.
    """
    assert settings.is_health_check_path("/health") is True
    assert settings.is_health_check_path("/health/") is True
    assert settings.is_health_check_path("/healthy") is False
    assert settings.is_health_check_path("/healthcheck") is False
    assert settings.is_health_check_path("/api/v1/health") is False
    assert settings.is_health_check_path("/api/v1/health-insurance") is False
