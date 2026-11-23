import httpx
import pytest

from app.models.inventory import Inventory
from app.models.supplier import Supplier
from tests.conftest import seed_sales_history

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
    assert response.json()["detail"] == "Forbidden: Insufficient permissions"


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
            "warehouse_id": "WH-BLR-01",
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
            "warehouse_id": "WH-BLR-01",
            "quantity_on_hand": 100,
            "lead_time_days": 5,
            "safety_stock": 10,
        },
        headers=auth_header(),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Forbidden: Insufficient permissions"


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
            "warehouse_id": "WH-BLR-01",
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
            "warehouse_id": "WH-BLR-01",
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
    fake_platform(exc=httpx.TimeoutException("Platform timeout"))

    response = client_raw.get(
        "/api/v1/inventory",
        headers=auth_header(),
    )

    assert response.status_code == 503
    assert "timed out" in response.json()["detail"].lower()


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


# ============================================================
# FLOW A & PURCHASE ORDER PERMISSIONS
# ============================================================


def test_purchase_order_create_permission_denied_for_supplier(
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

    response = client_raw.post(
        "/api/v1/inventory/purchase-orders/draft",
        json={"sku_id": "SKU-000001", "warehouse_id": "WH-BLR-01"},
        headers=auth_header(),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Forbidden: Insufficient permissions"


def test_purchase_order_create_permission_denied_for_inventory_write_only(
    client_raw,
    fake_platform,
):
    """Roles with inventory:write but without purchase_order:create (e.g. warehouse_manager) are rejected."""
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
        "/api/v1/inventory/purchase-orders/draft",
        json={"sku_id": "SKU-000001", "warehouse_id": "WH-BLR-01"},
        headers=auth_header(),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Forbidden: Insufficient permissions"


def test_flow_a_procurement_manager_passes_a1_a2_and_a3(
    client_raw,
    fake_platform,
    db_session,
):
    """
    Flow A end-to-end authorization check:
    Procurement manager token with inventory:read and purchase_order:create
    successfully runs:
      A1: GET /api/v1/inventory/optimization/recommendations (HTTP 200)
      A2: POST /api/v1/inventory/purchase-orders/draft (HTTP 201)
      A3: POST /api/v1/inventory/purchase-orders/{po_id}/approve (HTTP 200)
    """
    sku = "SKU-000999"
    wh = "WH-BLR-01"

    db_session.add(
        Inventory(
            sku_id=sku,
            product_name="Flow A Product",
            warehouse_id=wh,
            category="Electronics",
            quantity_on_hand=5,
            lead_time_days=5,
            safety_stock=10,
            warehouse_type="local",
        )
    )
    db_session.add(
        Supplier(
            supplier_id="SUP-00099",
            supplier_name="Flow A Supplier",
            sku_id=sku,
            unit_cost=50.0,
            lead_time_days=5,
        )
    )
    db_session.commit()
    seed_sales_history(sku, wh, daily_quantity=10, days=30)

    fake_platform(
        200,
        {
            "valid": True,
            "role": "procurement_manager",
            "user_id": 42,
            "permissions": [
                "supplier:read",
                "supplier:write",
                "inventory:read",
                "purchase_order:create",
            ],
        },
    )

    # Step A1: recommendations (requires inventory:read)
    res_a1 = client_raw.get(
        "/api/v1/inventory/optimization/recommendations",
        headers=auth_header(),
    )
    assert res_a1.status_code == 200, res_a1.text

    # Step A2: draft purchase order (requires purchase_order:create)
    res_a2 = client_raw.post(
        "/api/v1/inventory/purchase-orders/draft",
        json={"sku_id": sku, "warehouse_id": wh},
        headers=auth_header(),
    )
    assert res_a2.status_code == 201, res_a2.text
    po_id = res_a2.json()["po_id"]

    # Step A3: approve purchase order (requires procurement_manager role)
    res_a3 = client_raw.post(
        f"/api/v1/inventory/purchase-orders/{po_id}/approve",
        headers=auth_header(),
    )
    assert res_a3.status_code == 200, res_a3.text
    assert res_a3.json()["approval_status"] == "approved"


def test_flow_a_unauthorized_role_denied_a1_and_a2(
    client_raw,
    fake_platform,
):
    """
    A role without inventory:read and purchase_order:create (e.g. supplier)
    gets 403 Forbidden on both A1 and A2.
    """
    fake_platform(
        200,
        {
            "valid": True,
            "role": "supplier",
            "user_id": 99,
            "permissions": [
                "supplier:read",
                "supplier:write",
            ],
        },
    )

    res_a1 = client_raw.get(
        "/api/v1/inventory/optimization/recommendations",
        headers=auth_header(),
    )
    assert res_a1.status_code == 403
    assert res_a1.json()["detail"] == "Forbidden: Insufficient permissions"

    res_a2 = client_raw.post(
        "/api/v1/inventory/purchase-orders/draft",
        json={"sku_id": "SKU-000001", "warehouse_id": "WH-BLR-01"},
        headers=auth_header(),
    )
    assert res_a2.status_code == 403
    assert res_a2.json()["detail"] == "Forbidden: Insufficient permissions"
