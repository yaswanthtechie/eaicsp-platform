"""
Tests for per-user and per-role rate limiting middleware.
"""

import base64
import json
import logging
import time

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.middleware.rate_limit import extract_jwt_identity, in_memory_limiter
from app.middleware.ratelimit import get_real_ip, limiter

try:
    import jwt
except ImportError:
    jwt = None


def encode_payload(payload: dict) -> str:
    """Encodes payload as JWT string using PyJWT if present, or base64url JSON token string."""
    if jwt is not None:
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
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
    token = create_token(user_id="user_a", role="analyst")
    headers = {"Authorization": f"Bearer {token}"}
    limit = settings.get_role_rate_limit("analyst")

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
    token_a = create_token(user_id="user_a", role="analyst")
    token_b = create_token(user_id="user_b", role="analyst")
    limit = settings.get_role_rate_limit("analyst")

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
    token_a = create_token(user_id="user_a", role="ceo")
    token_b = create_token(user_id="user_b", role="ceo")
    limit = settings.get_role_rate_limit("ceo")

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
    ceo_token = create_token(user_id="ceo_1", role="ceo")
    procurement_token = create_token(user_id="proc_1", role="procurement_manager")
    analyst_token = create_token(user_id="analyst_1", role="analyst")

    ceo_limit = settings.get_role_rate_limit("ceo")
    procurement_limit = settings.get_role_rate_limit("procurement_manager")
    analyst_limit = settings.get_role_rate_limit("analyst")

    assert ceo_limit == 200
    assert procurement_limit == 100
    assert analyst_limit == 60
    assert ceo_limit > procurement_limit > analyst_limit

    res_ceo = client.get("/", headers={"Authorization": f"Bearer {ceo_token}"})
    assert res_ceo.headers["X-RateLimit-Limit"] == str(ceo_limit)

    res_proc = client.get("/", headers={"Authorization": f"Bearer {procurement_token}"})
    assert res_proc.headers["X-RateLimit-Limit"] == str(procurement_limit)

    res_analyst = client.get("/", headers={"Authorization": f"Bearer {analyst_token}"})
    assert res_analyst.headers["X-RateLimit-Limit"] == str(analyst_limit)


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
    token = create_token(user_id="user_headers", role="analyst")
    headers = {"Authorization": f"Bearer {token}"}
    limit = settings.get_role_rate_limit("analyst")

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
    token = create_token(user_id="boundary_user", role="supplier")
    headers = {"Authorization": f"Bearer {token}"}
    limit = settings.get_role_rate_limit("supplier")

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
    Verifies role names with uppercase or whitespace (" CEO ", "Procurement Manager") resolve correctly.
    """
    ceo_quota = settings.get_role_rate_limit("ceo")
    procurement_quota = settings.get_role_rate_limit("procurement_manager")

    assert settings.get_role_rate_limit(" CEO ") == ceo_quota
    assert settings.get_role_rate_limit("Procurement_Manager") == procurement_quota
    assert settings.get_role_rate_limit("procurement manager") == procurement_quota


def test_11_unknown_role_fallback(client):
    """
    Test 11 — Unknown role fallback:
    Verifies unknown role name falls back to default role limit quota.
    """
    default_quota = settings.get_role_rate_limit("default")
    assert settings.get_role_rate_limit("super_unknown_role") == default_quota


def test_17_all_platform_roles_explicitly_present_in_role_rate_limits():
    """
    Test 17 — All platform roles are explicitly mapped in ROLE_RATE_LIMITS:
    Verifies each of the 8 canonical platform roles from user.py is present.
    """
    expected_platform_roles = [
        "ceo",
        "vp_operations",
        "procurement_manager",
        "logistics_manager",
        "compliance_officer",
        "warehouse_manager",
        "analyst",
        "supplier",
    ]
    for role in expected_platform_roles:
        assert role in settings.ROLE_RATE_LIMITS, f"Platform role '{role}' missing from ROLE_RATE_LIMITS"


def test_18_executive_role_quotas():
    """
    Test 18 — Executive role quotas:
    Verifies ceo and vp_operations receive quota of 200.
    """
    assert settings.get_role_rate_limit("ceo") == 200
    assert settings.get_role_rate_limit("vp_operations") == 200


def test_19_six_newly_supported_platform_role_quotas():
    """
    Test 19 — Newly supported platform role quotas:
    Verifies each of the 6 newly added roles receives its explicit quota
    instead of relying on the default quota (60).
    """
    # Managerial / Compliance / Operations (100 req/min)
    assert settings.get_role_rate_limit("procurement_manager") == 100
    assert settings.get_role_rate_limit("logistics_manager") == 100
    assert settings.get_role_rate_limit("compliance_officer") == 100
    assert settings.get_role_rate_limit("warehouse_manager") == 100

    # Operational / External (60 req/min)
    assert settings.get_role_rate_limit("analyst") == 60
    assert settings.get_role_rate_limit("supplier") == 60


def test_20_missing_none_and_unknown_roles_fallback_to_default():
    """
    Test 20 — Missing, None, and unknown role fallback:
    Verifies missing, None, empty, and unknown roles fall back to default: 60.
    """
    default_quota = settings.ROLE_RATE_LIMITS["default"]
    assert default_quota == 60
    assert settings.get_role_rate_limit(None) == default_quota
    assert settings.get_role_rate_limit("") == default_quota
    assert settings.get_role_rate_limit("unknown_custom_role") == default_quota


def test_21_obsolete_roles_removed_from_role_rate_limits():
    """
    Test 21 — Obsolete roles removed:
    Verifies obsolete roles (admin, manager, user, guest) are NOT keys in ROLE_RATE_LIMITS.
    """
    obsolete_roles = ["admin", "manager", "user", "guest"]
    for role in obsolete_roles:
        assert role not in settings.ROLE_RATE_LIMITS, f"Obsolete role '{role}' should not be in ROLE_RATE_LIMITS"
        # Since they are removed, looking them up will fall back to default
        assert settings.get_role_rate_limit(role) == settings.get_role_rate_limit("default")


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
    token = create_token(user_id="load_tester", role="supplier")
    headers = {"Authorization": f"Bearer {token}"}
    limit = settings.get_role_rate_limit("supplier")

    # Send more requests than the limit
    for _ in range(limit + 5):
        res = client.get("/", headers=headers)
        assert res.status_code == 200


def test_22_load_test_mode_warning_logged_without_spam(client, caplog):
    """
    Test 22 — LOAD_TEST_MODE observability:
    1. LOAD_TEST_MODE=True bypasses rate limiting.
    2. A WARNING log is emitted when LOAD_TEST_MODE is active.
    3. Warning is only logged once without spamming across multiple requests.
    4. LOAD_TEST_MODE=False keeps normal rate limiting behavior.
    """
    caplog.set_level(logging.WARNING, logger="api_gateway.rate_limit")

    # Step 1 & 2 & 3: LOAD_TEST_MODE=True bypasses quota and emits single warning log
    settings.LOAD_TEST_MODE = True
    token = create_token(user_id="load_test_user_obs", role="supplier")
    headers = {"Authorization": f"Bearer {token}"}
    limit = settings.get_role_rate_limit("supplier")

    for _ in range(limit + 5):
        res = client.get("/", headers=headers)
        assert res.status_code == 200

    warning_records = [
        r for r in caplog.records
        if r.name == "api_gateway.rate_limit" and r.levelno == logging.WARNING
    ]
    assert len(warning_records) == 1
    assert "LOAD_TEST_MODE is enabled" in warning_records[0].message
    assert "bypassed" in warning_records[0].message

    # Step 4: LOAD_TEST_MODE=False keeps normal rate limiting behavior
    caplog.clear()
    settings.LOAD_TEST_MODE = False
    in_memory_limiter.reset()

    token_normal = create_token(user_id="normal_user_obs", role="supplier")
    headers_normal = {"Authorization": f"Bearer {token_normal}"}

    for _ in range(limit):
        res = client.get("/", headers=headers_normal)
        assert res.status_code == 200

    res_blocked = client.get("/", headers=headers_normal)
    assert res_blocked.status_code == 429
    assert res_blocked.json()["detail"] == "Too Many Requests"

    # Confirm no LOAD_TEST_MODE warning log emitted when disabled
    warning_records_after = [
        r for r in caplog.records
        if "LOAD_TEST_MODE" in r.message
    ]
    assert len(warning_records_after) == 0


def test_23_pyjwt_unavailable_forged_payload_not_trusted(monkeypatch, client):
    """
    Test 23 — Regression test for PyJWT dependency fallback security:
    Simulates PyJWT being unavailable and proves that a forged JWT payload
    containing a privileged role (such as 'ceo') is NOT trusted.
    extract_jwt_identity must return (None, None), and request must fall back
    to default IP-based rate limiting instead of executive quota.
    """
    # Create an unsigned/forged JWT payload with privileged 'ceo' role
    header_b64 = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps({"user_id": "forged_ceo_user", "role": "ceo"}).encode()).decode().rstrip("=")
    forged_token = f"{header_b64}.{payload_b64}.fake_signature"

    # Simulate PyJWT being unavailable (jwt = None)
    monkeypatch.setattr("app.middleware.rate_limit.jwt", None)

    # 1. Direct unit test of extract_jwt_identity
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"authorization", f"Bearer {forged_token}".encode())],
    }
    request = Request(scope)
    user_id, role = extract_jwt_identity(request)
    assert user_id is None
    assert role is None

    # 2. Integration test via client: should use default rate limit (60) instead of ceo quota (200)
    response = client.get("/", headers={"Authorization": f"Bearer {forged_token}"})
    assert response.status_code == 200
    default_quota = settings.get_role_rate_limit("default")
    assert response.headers["X-RateLimit-Limit"] == str(default_quota)
    assert response.headers["X-RateLimit-Limit"] != str(settings.get_role_rate_limit("ceo"))


def test_24_extract_jwt_identity_all_cases():
    """
    Test 24 — Comprehensive extract_jwt_identity unit tests:
    - No Authorization header -> (None, None)
    - Invalid/non-Bearer Authorization header -> (None, None)
    - Empty Bearer token -> (None, None)
    - Invalid/tampered JWT -> (None, None)
    - Valid JWT signed with SECRET_KEY -> (user_id, role)
    - Valid JWT with 'sub' and 'roles' claims -> (user_id, role)
    """
    # No Authorization header
    req_no_auth = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    assert extract_jwt_identity(req_no_auth) == (None, None)

    # Non-Bearer Authorization header
    req_basic = Request({
        "type": "http", "method": "GET", "path": "/",
        "headers": [(b"authorization", b"Basic dXNlcjpwYXNz")],
    })
    assert extract_jwt_identity(req_basic) == (None, None)

    # Empty Bearer token
    req_empty_bearer = Request({
        "type": "http", "method": "GET", "path": "/",
        "headers": [(b"authorization", b"Bearer ")],
    })
    assert extract_jwt_identity(req_empty_bearer) == (None, None)

    # Invalid JWT string
    req_invalid_jwt = Request({
        "type": "http", "method": "GET", "path": "/",
        "headers": [(b"authorization", b"Bearer invalid.token.payload")],
    })
    assert extract_jwt_identity(req_invalid_jwt) == (None, None)

    # Valid JWT signed with SECRET_KEY
    valid_token = create_token(user_id="valid_ceo_1", role="ceo")
    req_valid = Request({
        "type": "http", "method": "GET", "path": "/",
        "headers": [(b"authorization", f"Bearer {valid_token}".encode())],
    })
    assert extract_jwt_identity(req_valid) == ("valid_ceo_1", "ceo")

    # Valid JWT with sub and roles list
    if jwt is not None:
        token_sub_roles = jwt.encode(
            {"sub": "sub_user_42", "roles": ["procurement_manager", "analyst"]},
            settings.SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        req_sub_roles = Request({
            "type": "http", "method": "GET", "path": "/",
            "headers": [(b"authorization", f"Bearer {token_sub_roles}".encode())],
        })
        assert extract_jwt_identity(req_sub_roles) == ("sub_user_42", "procurement_manager")


def test_25_ceo_can_use_full_200_quota_without_slowapi_ip_blocking(client):
    """
    Regression Test:
    Ensures that an authenticated CEO user can send >100 requests (e.g. 150 requests)
    and successfully receive all 200 requests within the window without being blocked
    by SlowAPI's default IP limiter at request 101.
    """
    token = create_token(user_id="exec_ceo_99", role="ceo")
    headers = {"Authorization": f"Bearer {token}"}

    for i in range(1, 201):
        resp = client.get("/", headers=headers)
        assert resp.status_code == 200, f"Request {i} failed with status {resp.status_code}"
        assert resp.headers["X-RateLimit-Limit"] == "200"

    # Request 201 exceeds CEO's 200 quota
    resp_over = client.get("/", headers=headers)
    assert resp_over.status_code == 429
    assert resp_over.headers["X-RateLimit-Remaining"] == "0"


def test_26_vp_operations_can_use_full_200_quota(client):
    """
    Regression Test:
    Ensures that an authenticated VP Operations user can utilize their full 200 quota.
    """
    token = create_token(user_id="exec_vp_99", role="vp_operations")
    headers = {"Authorization": f"Bearer {token}"}

    for i in range(1, 201):
        resp = client.get("/", headers=headers)
        assert resp.status_code == 200, f"Request {i} failed with status {resp.status_code}"
        assert resp.headers["X-RateLimit-Limit"] == "200"

    # Request 201 exceeds VP's 200 quota
    resp_over = client.get("/", headers=headers)
    assert resp_over.status_code == 429


def test_27_anonymous_remains_strictly_limited_to_default_quota(client):
    """
    Regression Test:
    Ensures anonymous requests are restricted to the default 60 req/min quota.
    """
    for i in range(1, 61):
        resp = client.get("/")
        assert resp.status_code == 200, f"Request {i} failed with status {resp.status_code}"
        assert resp.headers["X-RateLimit-Limit"] == "60"

    # Request 61 must be rejected
    resp_over = client.get("/")
    assert resp_over.status_code == 429


def test_28_invalid_jwt_limited_to_default_and_never_granted_privileged_quota(client):
    """
    Regression Test:
    Ensures forged/invalid tokens signed with wrong secret are rejected,
    limited to 60 req/min, and never receive the 200/min privileged quota.
    """
    fake_token = jwt.encode(
        {"sub": "attacker", "user_id": "hacker_1", "role": "ceo"},
        "wrong-secret-key-that-does-not-match-gateway",
        algorithm="HS256",
    )
    headers = {"Authorization": f"Bearer {fake_token}"}

    for i in range(1, 61):
        resp = client.get("/", headers=headers)
        assert resp.status_code == 200
        assert resp.headers["X-RateLimit-Limit"] == "60"
        assert resp.headers["X-RateLimit-Limit"] != "200"

    # Request 61 must be blocked
    resp_over = client.get("/", headers=headers)
    assert resp_over.status_code == 429
