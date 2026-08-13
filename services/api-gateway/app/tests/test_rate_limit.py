"""
Tests for per-user and per-role rate limiting middleware.
"""

import base64
import json
import time

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.middleware.rate_limit import in_memory_limiter
from app.middleware.ratelimit import get_real_ip, limiter

try:
    import jwt
except ImportError:
    jwt = None


def encode_payload(payload: dict) -> str:
    """Encodes payload as JWT string using PyJWT if present, or base64url JSON token string."""
    if jwt is not None:
        return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{header}.{body}.mock_signature"


def create_token(user_id=None, role=None):
    """Helper to generate JWT tokens for testing."""
    payload = {}
    if user_id is not None:
        payload["user_id"] = user_id
    if role is not None:
        payload["role"] = role
    return encode_payload(payload)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """
    Reset rate limiter state before and after each test.
    Temporarily disable slowapi global IP rate limiting during per-user/per-role
    rate limit unit tests to prevent test client IP collision across test functions.
    Also force LOAD_TEST_MODE to False to guarantee test isolation from environment.
    """
    in_memory_limiter.reset()
    limiter.enabled = False
    old_trusted = list(getattr(settings, "TRUSTED_PROXIES", []))
    settings.TRUSTED_PROXIES = []

    old_load_test_mode = getattr(settings, "LOAD_TEST_MODE", False)
    settings.LOAD_TEST_MODE = False

    yield

    in_memory_limiter.reset()
    limiter.enabled = True
    settings.TRUSTED_PROXIES = old_trusted
    settings.LOAD_TEST_MODE = old_load_test_mode


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_1_same_user_limit_exceeded(client):
    """
    Test 1 — Same user:
    Requests allowed up to limit, next request receives HTTP 429.
    """
    token = create_token(user_id="user_a", role="user")
    headers = {"Authorization": f"Bearer {token}"}
    limit = settings.get_role_rate_limit("user")

    for _ in range(limit):
        response = client.get("/", headers=headers)
        assert response.status_code == 200

    response = client.get("/", headers=headers)
    assert response.status_code == 429
    assert response.json()["detail"] == "Too Many Requests"


def test_2_different_users_separate_buckets(client):
    """
    Test 2 — Different users have separate buckets:
    User A reaches limit; User B is still allowed.
    """
    token_a = create_token(user_id="user_a", role="user")
    token_b = create_token(user_id="user_b", role="user")
    limit = settings.get_role_rate_limit("user")

    for _ in range(limit):
        res_a = client.get("/", headers={"Authorization": f"Bearer {token_a}"})
        assert res_a.status_code == 200

    res_a_over = client.get("/", headers={"Authorization": f"Bearer {token_a}"})
    assert res_a_over.status_code == 429

    res_b = client.get("/", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b.status_code == 200


def test_3_same_role_different_users_prioritizes_user_id(client):
    """
    Test 3 — Same role but different users:
    Verifies user_id is prioritized over role (user:<user_id>).
    """
    token_a = create_token(user_id="user_a", role="admin")
    token_b = create_token(user_id="user_b", role="admin")
    limit = settings.get_role_rate_limit("admin")

    for _ in range(limit):
        res_a = client.get("/", headers={"Authorization": f"Bearer {token_a}"})
        assert res_a.status_code == 200

    res_a_over = client.get("/", headers={"Authorization": f"Bearer {token_a}"})
    assert res_a_over.status_code == 429

    # User B has same role but separate user bucket
    res_b = client.get("/", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b.status_code == 200


def test_4_role_based_limits(client):
    """
    Test 4 — Role-based limits:
    Verifies different roles receive their configured quotas.
    """
    admin_token = create_token(user_id="admin_1", role="admin")
    user_token = create_token(user_id="user_1", role="user")

    admin_limit = settings.get_role_rate_limit("admin")
    user_limit = settings.get_role_rate_limit("user")

    assert admin_limit > user_limit

    res_admin = client.get("/", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.headers["X-RateLimit-Limit"] == str(admin_limit)

    res_user = client.get("/", headers={"Authorization": f"Bearer {user_token}"})
    assert res_user.headers["X-RateLimit-Limit"] == str(user_limit)


def test_5_no_jwt_fallback(client):
    """
    Test 5 — No JWT:
    Verifies unauthenticated requests fall back to IP-based identity safely.
    """
    response = client.get("/")
    assert response.status_code == 200
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers


def test_6_invalid_jwt_fallback(client):
    """
    Test 6 — Invalid JWT:
    Verifies invalid JWT does not crash the gateway and falls back safely.
    """
    headers = {"Authorization": "Bearer invalid.token.value"}
    response = client.get("/", headers=headers)
    assert response.status_code == 200
    assert "X-RateLimit-Limit" in response.headers


def test_7_rate_limit_headers(client):
    """
    Test 7 — Rate-limit headers:
    Verifies successful and rejected responses contain expected headers.
    """
    token = create_token(user_id="user_headers", role="user")
    headers = {"Authorization": f"Bearer {token}"}
    limit = settings.get_role_rate_limit("user")

    res1 = client.get("/", headers=headers)
    assert res1.status_code == 200
    assert res1.headers["X-RateLimit-Limit"] == str(limit)
    assert int(res1.headers["X-RateLimit-Remaining"]) == limit - 1

    for _ in range(limit - 1):
        client.get("/", headers=headers)

    res_rejected = client.get("/", headers=headers)
    assert res_rejected.status_code == 429
    assert res_rejected.headers["X-RateLimit-Limit"] == str(limit)
    assert res_rejected.headers["X-RateLimit-Remaining"] == "0"
    assert "Retry-After" in res_rejected.headers


def test_8_window_reset(client):
    """
    Test 8 — Window reset:
    After configured time window expires, identity can make requests again.
    """
    key = "user:user_reset"
    limit = 2
    short_window = 0.2

    allowed1, _, _, _ = in_memory_limiter.check_and_update(key, limit, short_window)
    assert allowed1 is True

    allowed2, _, _, _ = in_memory_limiter.check_and_update(key, limit, short_window)
    assert allowed2 is True

    allowed3, _, _, _ = in_memory_limiter.check_and_update(key, limit, short_window)
    assert allowed3 is False

    time.sleep(0.25)

    allowed4, _, _, _ = in_memory_limiter.check_and_update(key, limit, short_window)
    assert allowed4 is True


def test_9_exact_quota_boundary(client):
    """
    Test 9 — Exact quota boundary condition:
    Request count N equals limit succeeds; request N+1 fails with HTTP 429.
    """
    token = create_token(user_id="boundary_user", role="user")
    headers = {"Authorization": f"Bearer {token}"}
    limit = settings.get_role_rate_limit("user")

    for i in range(limit):
        res = client.get("/", headers=headers)
        assert res.status_code == 200
        assert int(res.headers["X-RateLimit-Remaining"]) == limit - (i + 1)

    # N+1 attempt
    res_boundary = client.get("/", headers=headers)
    assert res_boundary.status_code == 429
    assert res_boundary.headers["X-RateLimit-Remaining"] == "0"


def test_10_role_case_and_whitespace_normalization(client):
    """
    Test 10 — Role name normalization:
    Verifies role names with uppercase or whitespace (" ADMIN ", "Manager") resolve correctly.
    """
    admin_quota = settings.get_role_rate_limit("admin")
    manager_quota = settings.get_role_rate_limit("manager")

    assert settings.get_role_rate_limit(" ADMIN ") == admin_quota
    assert settings.get_role_rate_limit("Manager") == manager_quota


def test_11_unknown_role_fallback(client):
    """
    Test 11 — Unknown role fallback:
    Verifies unknown role name falls back to default role limit quota.
    """
    default_quota = settings.get_role_rate_limit("default")
    assert settings.get_role_rate_limit("super_unknown_role") == default_quota


def test_12_token_missing_claims(client):
    """
    Test 12 — Token missing user_id/sub claims:
    Verifies JWT token without user_id falls back safely to role or IP bucket.
    """
    payload = {"custom_field": "no_sub_or_user_id"}
    token = encode_payload(payload)
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/", headers=headers)
    assert res.status_code == 200
    assert "X-RateLimit-Limit" in res.headers


def test_13_rate_limit_thread_safety(client):
    """
    Test 13 — Thread safety:
    Verifies concurrent updates to in_memory_limiter state remain thread-safe.
    """
    import threading

    key = "concurrent_user"
    limit = 100
    window = 10.0
    threads = []
    successes = []

    def make_request():
        allowed, _, _, _ = in_memory_limiter.check_and_update(key, limit, window)
        if allowed:
            successes.append(1)

    for _ in range(limit + 20):
        t = threading.Thread(target=make_request)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert len(successes) == limit


def test_14_x_forwarded_for_spoofing_prevention_untrusted_proxy(client):
    """
    Test 14 — X-Forwarded-For spoofing prevention:
    Verifies that spoofed X-Forwarded-For headers from untrusted proxy IPs
    do NOT create new buckets and cannot bypass rate limiting.
    """
    settings.TRUSTED_PROXIES = []
    default_limit = settings.get_role_rate_limit("default")

    # Send requests with different spoofed X-Forwarded-For headers
    for i in range(default_limit):
        spoofed_headers = {"X-Forwarded-For": f"10.0.{i // 256}.{i % 256}"}
        res = client.get("/", headers=spoofed_headers)
        assert res.status_code == 200

    # Next request should be rate-limited despite new spoofed IP header
    spoofed_headers = {"X-Forwarded-For": "10.0.99.99"}
    res_rejected = client.get("/", headers=spoofed_headers)
    assert res_rejected.status_code == 429


def test_15_x_forwarded_for_trusted_proxy(client):
    """
    Test 15 — X-Forwarded-For header processing with trusted proxy:
    Verifies that when request comes from a trusted proxy IP, the client IP
    extracted from X-Forwarded-For is correctly used for identity rate-limiting.
    """
    settings.TRUSTED_PROXIES = ["127.0.0.1", "testclient"]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"x-forwarded-for", b"203.0.113.195")],
        "client": ("testclient", 12345),
    }
    request = Request(scope)

    ip = get_real_ip(request)
    assert ip == "203.0.113.195"


def test_16_load_test_mode_bypass(client):
    """
    Test 16 — Load test mode bypass:
    Verifies that when LOAD_TEST_MODE is enabled, rate limiting middleware is bypassed
    and allows requests beyond configured quota without returning 429.
    """
    settings.LOAD_TEST_MODE = True
    token = create_token(user_id="load_tester", role="user")
    headers = {"Authorization": f"Bearer {token}"}
    limit = settings.get_role_rate_limit("user")

    # Send more requests than the limit
    for _ in range(limit + 5):
        res = client.get("/", headers=headers)
        assert res.status_code == 200
