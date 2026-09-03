
import os

import httpx
import pytest

from app.core.config import settings


# =========================================================
# REAL TOKENS
# =========================================================
#
# These tokens must come from Rahul's real Platform Service.
# Keep them in environment variables.
#
# Do NOT put real JWT tokens directly in this file.
# =========================================================

WAREHOUSE_MANAGER_TOKEN = os.getenv(
    "WAREHOUSE_MANAGER_TOKEN"
)

PROCUREMENT_MANAGER_TOKEN = os.getenv(
    "PROCUREMENT_MANAGER_TOKEN"
)

CEO_TOKEN = os.getenv(
    "CEO_TOKEN"
)

VP_OPERATIONS_TOKEN = os.getenv(
    "VP_OPERATIONS_TOKEN"
)

EXPIRED_TOKEN = os.getenv(
    "EXPIRED_TOKEN"
)


# =========================================================
# HELPER
# =========================================================


def auth_header(token: str):
    return {
        "Authorization": f"Bearer {token}"
    }


# =========================================================
# BULK-UPDATE
#
# Allowed roles:
#   warehouse_manager
#   procurement_manager
# =========================================================


def test_bulk_update_missing_token(client_raw):

    response = client_raw.post(
        "/api/v1/inventory/bulk-update",
        json=[],
    )

    assert response.status_code == 401


def test_bulk_update_malformed_token(client_raw):

    response = client_raw.post(
        "/api/v1/inventory/bulk-update",
        json=[],
        headers=auth_header(
            "invalid-token"
        ),
    )

    assert response.status_code == 401


@pytest.mark.skipif(
    not WAREHOUSE_MANAGER_TOKEN,
    reason="WAREHOUSE_MANAGER_TOKEN not configured",
)
def test_bulk_update_warehouse_manager_success(client_raw):

    response = client_raw.post(
        "/api/v1/inventory/bulk-update",
        json=[],
        headers=auth_header(
            WAREHOUSE_MANAGER_TOKEN
        ),
    )

    assert response.status_code not in [
        401,
        403,
    ]


@pytest.mark.skipif(
    not PROCUREMENT_MANAGER_TOKEN,
    reason="PROCUREMENT_MANAGER_TOKEN not configured",
)
def test_bulk_update_procurement_manager_success(client_raw):

    response = client_raw.post(
        "/api/v1/inventory/bulk-update",
        json=[],
        headers=auth_header(
            PROCUREMENT_MANAGER_TOKEN
        ),
    )

    assert response.status_code not in [
        401,
        403,
    ]


@pytest.mark.skipif(
    not CEO_TOKEN,
    reason="CEO_TOKEN not configured",
)
def test_bulk_update_ceo_wrong_role(client_raw):

    response = client_raw.post(
        "/api/v1/inventory/bulk-update",
        json=[],
        headers=auth_header(
            CEO_TOKEN
        ),
    )

    assert response.status_code == 403


@pytest.mark.skipif(
    not VP_OPERATIONS_TOKEN,
    reason="VP_OPERATIONS_TOKEN not configured",
)
def test_bulk_update_vp_operations_wrong_role(client_raw):

    response = client_raw.post(
        "/api/v1/inventory/bulk-update",
        json=[],
        headers=auth_header(
            VP_OPERATIONS_TOKEN
        ),
    )

    assert response.status_code == 403


# =========================================================
# BULK-UPLOAD
#
# Allowed roles:
#   warehouse_manager
#   procurement_manager
# =========================================================


def test_bulk_upload_missing_token(client_raw):

    response = client_raw.post(
        "/api/v1/inventory/bulk-upload",
        files={
            "file": (
                "test.csv",
                (
                    b"sku_id,warehouse_id,"
                    b"quantity_delta\n"
                    b"TEST1,WH1,10\n"
                ),
                "text/csv",
            )
        },
    )

    assert response.status_code == 401


def test_bulk_upload_malformed_token(client_raw):

    response = client_raw.post(
        "/api/v1/inventory/bulk-upload",
        files={
            "file": (
                "test.csv",
                (
                    b"sku_id,warehouse_id,"
                    b"quantity_delta\n"
                    b"TEST1,WH1,10\n"
                ),
                "text/csv",
            )
        },
        headers=auth_header(
            "invalid-token"
        ),
    )

    assert response.status_code == 401


@pytest.mark.skipif(
    not WAREHOUSE_MANAGER_TOKEN,
    reason="WAREHOUSE_MANAGER_TOKEN not configured",
)
def test_bulk_upload_warehouse_manager_success(client_raw):

    response = client_raw.post(
        "/api/v1/inventory/bulk-upload",
        files={
            "file": (
                "test.csv",
                (
                    b"sku_id,warehouse_id,"
                    b"quantity_delta\n"
                    b"TEST1,WH1,10\n"
                ),
                "text/csv",
            )
        },
        headers=auth_header(
            WAREHOUSE_MANAGER_TOKEN
        ),
    )

    assert response.status_code not in [
        401,
        403,
    ]


@pytest.mark.skipif(
    not PROCUREMENT_MANAGER_TOKEN,
    reason="PROCUREMENT_MANAGER_TOKEN not configured",
)
def test_bulk_upload_procurement_manager_success(client_raw):

    response = client_raw.post(
        "/api/v1/inventory/bulk-upload",
        files={
            "file": (
                "test.csv",
                (
                    b"sku_id,warehouse_id,"
                    b"quantity_delta\n"
                    b"TEST1,WH1,10\n"
                ),
                "text/csv",
            )
        },
        headers=auth_header(
            PROCUREMENT_MANAGER_TOKEN
        ),
    )

    assert response.status_code not in [
        401,
        403,
    ]


@pytest.mark.skipif(
    not CEO_TOKEN,
    reason="CEO_TOKEN not configured",
)
def test_bulk_upload_ceo_wrong_role(client_raw):

    response = client_raw.post(
        "/api/v1/inventory/bulk-upload",
        files={
            "file": (
                "test.csv",
                (
                    b"sku_id,warehouse_id,"
                    b"quantity_delta\n"
                    b"TEST1,WH1,10\n"
                ),
                "text/csv",
            )
        },
        headers=auth_header(
            CEO_TOKEN
        ),
    )

    assert response.status_code == 403


@pytest.mark.skipif(
    not VP_OPERATIONS_TOKEN,
    reason="VP_OPERATIONS_TOKEN not configured",
)
def test_bulk_upload_vp_operations_wrong_role(client_raw):

    response = client_raw.post(
        "/api/v1/inventory/bulk-upload",
        files={
            "file": (
                "test.csv",
                (
                    b"sku_id,warehouse_id,"
                    b"quantity_delta\n"
                    b"TEST1,WH1,10\n"
                ),
                "text/csv",
            )
        },
        headers=auth_header(
            VP_OPERATIONS_TOKEN
        ),
    )

    assert response.status_code == 403


# =========================================================
# WHAT-IF
#
# Allowed roles:
#   ceo
#   vp_operations
# =========================================================


def test_what_if_missing_token(client_raw):

    response = client_raw.post(
        "/api/v1/inventory/what-if",
        json={
            "spike_percent": 30
        },
    )

    assert response.status_code == 401


def test_what_if_malformed_token(client_raw):

    response = client_raw.post(
        "/api/v1/inventory/what-if",
        json={
            "spike_percent": 30
        },
        headers=auth_header(
            "invalid-token"
        ),
    )

    assert response.status_code == 401


@pytest.mark.skipif(
    not CEO_TOKEN,
    reason="CEO_TOKEN not configured",
)
def test_what_if_ceo_success(client_raw):

    response = client_raw.post(
        "/api/v1/inventory/what-if",
        json={
            "spike_percent": 30
        },
        headers=auth_header(
            CEO_TOKEN
        ),
    )

    assert response.status_code not in [
        401,
        403,
    ]


@pytest.mark.skipif(
    not VP_OPERATIONS_TOKEN,
    reason="VP_OPERATIONS_TOKEN not configured",
)
def test_what_if_vp_operations_success(client_raw):

    response = client_raw.post(
        "/api/v1/inventory/what-if",
        json={
            "spike_percent": 30
        },
        headers=auth_header(
            VP_OPERATIONS_TOKEN
        ),
    )

    assert response.status_code not in [
        401,
        403,
    ]


@pytest.mark.skipif(
    not WAREHOUSE_MANAGER_TOKEN,
    reason="WAREHOUSE_MANAGER_TOKEN not configured",
)
def test_what_if_warehouse_manager_wrong_role(client_raw):

    response = client_raw.post(
        "/api/v1/inventory/what-if",
        json={
            "spike_percent": 30
        },
        headers=auth_header(
            WAREHOUSE_MANAGER_TOKEN
        ),
    )

    assert response.status_code == 403


@pytest.mark.skipif(
    not PROCUREMENT_MANAGER_TOKEN,
    reason="PROCUREMENT_MANAGER_TOKEN not configured",
)
def test_what_if_procurement_manager_wrong_role(client_raw):

    response = client_raw.post(
        "/api/v1/inventory/what-if",
        json={
            "spike_percent": 30
        },
        headers=auth_header(
            PROCUREMENT_MANAGER_TOKEN
        ),
    )

    assert response.status_code == 403


# =========================================================
# EXPIRED TOKEN
# =========================================================


@pytest.mark.skipif(
    not EXPIRED_TOKEN,
    reason="EXPIRED_TOKEN not configured",
)
def test_what_if_expired_token(client_raw):

    response = client_raw.post(
        "/api/v1/inventory/what-if",
        json={
            "spike_percent": 30
        },
        headers=auth_header(
            EXPIRED_TOKEN
        ),
    )

    assert response.status_code == 401


# =========================================================
# AUTH SERVICE UNAVAILABLE
# =========================================================


def test_auth_service_unavailable(
    client_raw,
    monkeypatch,
):

    monkeypatch.setattr(
        settings,
        "PLATFORM_AUTH_URL",
        "http://127.0.0.1:8999",
    )

    response = client_raw.post(
        "/api/v1/inventory/what-if",
        json={
            "spike_percent": 30
        },
        headers=auth_header(
            "test-token"
        ),
    )

    assert response.status_code == 503

    detail = response.json()["detail"]

    assert "Authentication service" in detail


# =========================================================
# AUTH SERVICE TIMEOUT
# =========================================================


def test_auth_service_timeout(
    client_raw,
    monkeypatch,
):

    async def fake_post(
        *args,
        **kwargs,
    ):
        raise httpx.TimeoutException(
            "Authentication service timed out"
        )

    monkeypatch.setattr(
        httpx.AsyncClient,
        "post",
        fake_post,
    )

    response = client_raw.post(
        "/api/v1/inventory/what-if",
        json={
            "spike_percent": 30
        },
        headers=auth_header(
            "test-token"
        ),
    )

    assert response.status_code == 503

    detail = response.json()["detail"]

    assert "timed out" in detail.lower()


# =========================================================
# FAKE PLATFORM SERVICE
#
# These tests do NOT require Rahul's Platform Service.
# They simulate its responses.
# =========================================================


class _FakeResponse:

    def __init__(
        self,
        status_code,
        payload=None,
    ):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


@pytest.fixture
def fake_platform(monkeypatch):

    def _install(
        status_code=200,
        payload=None,
        exc=None,
    ):

        async def _fake_post(
            self,
            url,
            **kwargs,
        ):

            if exc:
                raise exc

            return _FakeResponse(
                status_code,
                payload,
            )

        monkeypatch.setattr(
            httpx.AsyncClient,
            "post",
            _fake_post,
        )

    return _install


# =========================================================
# INVALID TOKEN -> 401
# =========================================================


def test_invalid_token_returns_401(
    client_raw,
    fake_platform,
):

    fake_platform(
        status_code=401
    )

    response = client_raw.post(
        "/api/v1/inventory/what-if",
        json={
            "spike_percent": 30
        },
        headers=auth_header(
            "bad-token"
        ),
    )

    assert response.status_code == 401


# =========================================================
# WRONG ROLE -> 403
# =========================================================


def test_wrong_role_returns_403(
    client_raw,
    fake_platform,
):

    fake_platform(
        200,
        {
            "valid": True,
            "role": "analyst",
        },
    )

    response = client_raw.post(
        "/api/v1/inventory/what-if",
        json={
            "spike_percent": 30
        },
        headers=auth_header(
            "test-token"
        ),
    )

    assert response.status_code == 403


# =========================================================
# CORRECT ROLE -> SUCCESS
# =========================================================


def test_correct_role_succeeds(
    client_raw,
    fake_platform,
):

    fake_platform(
        200,
        {
            "valid": True,
            "role": "ceo",
        },
    )

    response = client_raw.post(
        "/api/v1/inventory/what-if",
        json={
            "spike_percent": 30
        },
        headers=auth_header(
            "test-token"
        ),
    )

    assert response.status_code not in [
        401,
        403,
    ]


# =========================================================
# AUTH TIMEOUT -> 503
# =========================================================


def test_timeout_returns_503(
    client_raw,
    fake_platform,
):

    fake_platform(
        exc=httpx.TimeoutException(
            "slow"
        )
    )

    response = client_raw.post(
        "/api/v1/inventory/what-if",
        json={
            "spike_percent": 30
        },
        headers=auth_header(
            "test-token"
        ),
    )

    assert response.status_code == 503

    assert (
        "timed out"
        in response.json()["detail"].lower()
    )
