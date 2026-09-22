import httpx
import pytest


# ============================================================
# FAKE PLATFORM RESPONSE
# ============================================================

class _FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


# ============================================================
# FAKE PLATFORM AUTH
# ============================================================

@pytest.fixture
def fake_platform(monkeypatch):
    def _install(status_code=200, payload=None, exc=None):

        async def _fake_post(self, url, **kwargs):
            if exc:
                raise exc

            return _FakeResponse(
                status_code=status_code,
                payload=payload,
            )

        monkeypatch.setattr(
            httpx.AsyncClient,
            "post",
            _fake_post,
        )

    return _install


# ============================================================
# AUTH HEADER HELPER
# ============================================================

def auth_header(token="test-token"):
    return {
        "Authorization": f"Bearer {token}",
    }


# ============================================================
# INVENTORY READ PERMISSION
# ============================================================

def test_inventory_read_permission_allowed(
    client_raw,
    fake_platform,
):
    fake_platform(
        200,
        {
            "valid": True,
            "role": "analyst",
            "user_id": 1,
            "permissions": [
                "inventory:read",
            ],
        },
    )

    response = client_raw.get(
        "/api/v1/inventory",
        headers=auth_header(),
    )

    assert response.status_code == 200


def test_inventory_read_permission_denied(
    client_raw,
    fake_platform,
):
    fake_platform(
        200,
        {
            "valid": True,
            "role": "supplier",
            "user_id": 1,
            "permissions": [
                "supplier:read",
                "supplier:write",
            ],
        },
    )

    response = client_raw.get(
        "/api/v1/inventory",
        headers=auth_header(),
    )

    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "Forbidden: Insufficient permissions"
    )


# ============================================================
# INVENTORY WRITE PERMISSION
# ============================================================

def test_inventory_write_permission_allowed(
    client_raw,
    fake_platform,
):
    fake_platform(
        200,
        {
            "valid": True,
            "role": "warehouse_manager",
            "user_id": 1,
            "permissions": [
                "inventory:read",
                "inventory:write",
            ],
        },
    )

    response = client_raw.post(
        "/api/v1/inventory/",
        json={
            "sku_id": "M5-WRITE-001",
            "product_name": "M5 Permission Product",
            "warehouse_id": "WH001",
            "quantity_on_hand": 100,
            "lead_time_days": 5,
            "safety_stock": 10,
        },
        headers=auth_header(),
    )

    assert response.status_code == 201


def test_inventory_write_permission_denied(
    client_raw,
    fake_platform,
):
    fake_platform(
        200,
        {
            "valid": True,
            "role": "analyst",
            "user_id": 1,
            "permissions": [
                "inventory:read",
            ],
        },
    )

    response = client_raw.post(
        "/api/v1/inventory/",
        json={
            "sku_id": "M5-WRITE-DENIED",
            "product_name": "M5 Permission Product",
            "warehouse_id": "WH001",
            "quantity_on_hand": 100,
            "lead_time_days": 5,
            "safety_stock": 10,
        },
        headers=auth_header(),
    )

    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "Forbidden: Insufficient permissions"
    )


# ============================================================
# ANALYST PERMISSIONS
# ============================================================

def test_analyst_can_read_inventory(
    client_raw,
    fake_platform,
):
    fake_platform(
        200,
        {
            "valid": True,
            "role": "analyst",
            "user_id": 1,
            "permissions": [
                "inventory:read",
            ],
        },
    )

    response = client_raw.get(
        "/api/v1/inventory",
        headers=auth_header(),
    )

    assert response.status_code == 200


def test_analyst_cannot_write_inventory(
    client_raw,
    fake_platform,
):
    fake_platform(
        200,
        {
            "valid": True,
            "role": "analyst",
            "user_id": 1,
            "permissions": [
                "inventory:read",
            ],
        },
    )

    response = client_raw.post(
        "/api/v1/inventory/",
        json={
            "sku_id": "ANALYST-WRITE-001",
            "product_name": "Analyst Write Test",
            "warehouse_id": "WH001",
            "quantity_on_hand": 100,
            "lead_time_days": 5,
            "safety_stock": 10,
        },
        headers=auth_header(),
    )

    assert response.status_code == 403


# ============================================================
# CEO PERMISSIONS
# ============================================================

def test_ceo_has_inventory_read_and_write(
    client_raw,
    fake_platform,
):
    fake_platform(
        200,
        {
            "valid": True,
            "role": "ceo",
            "user_id": 1,
            "permissions": [
                "inventory:read",
                "inventory:write",
            ],
        },
    )

    read_response = client_raw.get(
        "/api/v1/inventory",
        headers=auth_header(),
    )

    assert read_response.status_code == 200

    write_response = client_raw.post(
        "/api/v1/inventory/",
        json={
            "sku_id": "CEO-M5-001",
            "product_name": "CEO M5 Product",
            "warehouse_id": "WH001",
            "quantity_on_hand": 100,
            "lead_time_days": 5,
            "safety_stock": 10,
        },
        headers=auth_header(),
    )

    assert write_response.status_code == 201


# ============================================================
# MISSING TOKEN
# ============================================================

def test_missing_token_returns_401(client_raw):
    response = client_raw.get(
        "/api/v1/inventory",
    )

    assert response.status_code == 401


# ============================================================
# INVALID TOKEN
# ============================================================

def test_invalid_token_returns_401(
    client_raw,
    fake_platform,
):
    fake_platform(
        401,
        {
            "valid": False,
        },
    )

    response = client_raw.get(
        "/api/v1/inventory",
        headers=auth_header("invalid-token"),
    )

    assert response.status_code == 401


# ============================================================
# PLATFORM TIMEOUT
# ============================================================

def test_platform_timeout_returns_503(
    client_raw,
    fake_platform,
):
    fake_platform(
        exc=httpx.TimeoutException(
            "Platform timeout"
        )
    )

    response = client_raw.get(
        "/api/v1/inventory",
        headers=auth_header(),
    )

    assert response.status_code == 503
    assert (
        "timed out"
        in response.json()["detail"].lower()
    )


# ============================================================
# BULK UPDATE ROLE ACCESS
# ============================================================

def test_bulk_update_allows_warehouse_manager(
    client_raw,
    fake_platform,
):
    fake_platform(
        200,
        {
            "valid": True,
            "role": "warehouse_manager",
            "user_id": 1,
            "permissions": [
                "inventory:read",
                "inventory:write",
            ],
        },
    )

    response = client_raw.post(
        "/api/v1/inventory/bulk-update",
        json=[],
        headers=auth_header(),
    )

    assert response.status_code != 401
    assert response.status_code != 403


def test_bulk_update_allows_procurement_manager(
    client_raw,
    fake_platform,
):
    fake_platform(
        200,
        {
            "valid": True,
            "role": "procurement_manager",
            "user_id": 1,
            "permissions": [
                "supplier:read",
                "supplier:write",
            ],
        },
    )

    response = client_raw.post(
        "/api/v1/inventory/bulk-update",
        json=[],
        headers=auth_header(),
    )

    assert response.status_code != 401
    assert response.status_code != 403


def test_bulk_update_rejects_analyst(
    client_raw,
    fake_platform,
):
    fake_platform(
        200,
        {
            "valid": True,
            "role": "analyst",
            "user_id": 1,
            "permissions": [
                "inventory:read",
            ],
        },
    )

    response = client_raw.post(
        "/api/v1/inventory/bulk-update",
        json=[],
        headers=auth_header(),
    )

    assert response.status_code == 403


# ============================================================
# WHAT-IF ROLE ACCESS
# ============================================================

def test_what_if_allows_ceo(
    client_raw,
    fake_platform,
):
    fake_platform(
        200,
        {
            "valid": True,
            "role": "ceo",
            "user_id": 1,
            "permissions": [
                "inventory:read",
                "inventory:write",
            ],
        },
    )

    response = client_raw.post(
        "/api/v1/inventory/what-if",
        json={
            "spike_percent": 30,
        },
        headers=auth_header(),
    )

    assert response.status_code != 401
    assert response.status_code != 403


def test_what_if_rejects_analyst(
    client_raw,
    fake_platform,
):
    fake_platform(
        200,
        {
            "valid": True,
            "role": "analyst",
            "user_id": 1,
            "permissions": [
                "inventory:read",
            ],
        },
    )

    response = client_raw.post(
        "/api/v1/inventory/what-if",
        json={
            "spike_percent": 30,
        },
        headers=auth_header(),
    )

    assert response.status_code == 403