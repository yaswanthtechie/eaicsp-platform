import os

import httpx
import pytest

from app.core.config import settings


# =========================================================
# REAL TOKENS
# =========================================================
#
# These values are read from environment variables.
# Do NOT put real JWT tokens directly in this file.
#
# Tokens must come from Rahul's real Platform Service.
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
# Allowed roles:
#   warehouse_manager
#   procurement_manager
# =========================================================


def test_bulk_update_missing_token(client):

    response = client.put(
        "/api/v1/inventory/bulk-update",
        json=[],
    )

    assert response.status_code == 401


def test_bulk_update_malformed_token(client):

    response = client.put(
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
def test_bulk_update_warehouse_manager_success(client):

    response = client.put(
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
def test_bulk_update_procurement_manager_success(client):

    response = client.put(
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
def test_bulk_update_ceo_wrong_role(client):

    response = client.put(
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
def test_bulk_update_vp_operations_wrong_role(client):

    response = client.put(
        "/api/v1/inventory/bulk-update",
        json=[],
        headers=auth_header(
            VP_OPERATIONS_TOKEN
        ),
    )

    assert response.status_code == 403


# =========================================================
# BULK-UPLOAD
# Allowed roles:
#   warehouse_manager
#   procurement_manager
# =========================================================


def test_bulk_upload_missing_token(client):

    response = client.post(
        "/api/v1/inventory/bulk-upload",
        files={
            "file": (
                "test.csv",
                b"",
                "text/csv",
            )
        },
    )

    assert response.status_code == 401


def test_bulk_upload_malformed_token(client):

    response = client.post(
        "/api/v1/inventory/bulk-upload",
        files={
            "file": (
                "test.csv",
                b"",
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
def test_bulk_upload_warehouse_manager_success(client):

    response = client.post(
        "/api/v1/inventory/bulk-upload",
        files={
            "file": (
                "test.csv",
                b"",
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
def test_bulk_upload_procurement_manager_success(client):

    response = client.post(
        "/api/v1/inventory/bulk-upload",
        files={
            "file": (
                "test.csv",
                b"",
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
def test_bulk_upload_ceo_wrong_role(client):

    response = client.post(
        "/api/v1/inventory/bulk-upload",
        files={
            "file": (
                "test.csv",
                b"",
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
def test_bulk_upload_vp_operations_wrong_role(client):

    response = client.post(
        "/api/v1/inventory/bulk-upload",
        files={
            "file": (
                "test.csv",
                b"",
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
# Allowed roles:
#   ceo
#   vp_operations
# =========================================================


def test_what_if_missing_token(client):

    response = client.post(
        "/api/v1/inventory/what-if",
        json={
            "spike_percent": 30
        },
    )

    assert response.status_code == 401


def test_what_if_malformed_token(client):

    response = client.post(
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
def test_what_if_ceo_success(client):

    response = client.post(
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
def test_what_if_vp_operations_success(client):

    response = client.post(
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
def test_what_if_warehouse_manager_wrong_role(client):

    response = client.post(
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
def test_what_if_procurement_manager_wrong_role(client):

    response = client.post(
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
def test_what_if_expired_token(client):

    response = client.post(
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
    client,
    monkeypatch,
):

    monkeypatch.setattr(
        settings,
        "PLATFORM_AUTH_URL",
        "http://127.0.0.1:8999",
    )

    response = client.post(
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
    client,
    monkeypatch,
):

    async def fake_get(
        *args,
        **kwargs,
    ):
        raise httpx.TimeoutException(
            "Authentication service timed out"
        )

    monkeypatch.setattr(
        httpx.AsyncClient,
        "get",
        fake_get,
    )

    response = client.post(
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