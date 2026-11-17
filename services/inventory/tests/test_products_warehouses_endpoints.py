"""Tests for Product and Warehouse read-only master data endpoints (R15 / #353 / #354)."""

from __future__ import annotations

from app.core.auth import verify_token
from app.main import app
from app.models.product import Product
from app.models.warehouse import Warehouse


def _seed_products(db_session, count: int = 5) -> list[Product]:
    products = [
        Product(
            sku_id=f"SKU-{i:06d}",
            name=f"Synthetic Product {i}",
            category="Electronics" if i % 2 == 0 else "Hardware",
            unit_of_measure="PCS",
            unit_cost=10.0 * i,
            unit_price=15.0 * i,
            is_active=True,
        )
        for i in range(1, count + 1)
    ]
    db_session.add_all(products)
    db_session.commit()
    return products


def _seed_warehouses(db_session, count: int = 4) -> list[Warehouse]:
    cities = [
        ("BLR", "Bangalore", "Karnataka"),
        ("BOM", "Mumbai", "Maharashtra"),
        ("DEL", "Delhi", "Delhi"),
        ("HYD", "Hyderabad", "Telangana"),
    ]
    warehouses = [
        Warehouse(
            warehouse_id=f"WH-{cities[i % len(cities)][0]}-01",
            name=f"{cities[i % len(cities)][1]} Warehouse",
            city=cities[i % len(cities)][1],
            state=cities[i % len(cities)][2],
            country="India",
            warehouse_type="regional",
            capacity_units=10000,
        )
        for i in range(min(count, len(cities)))
    ]
    db_session.add_all(warehouses)
    db_session.commit()
    return warehouses


# 1. Products list
def test_get_products_list_success(client, db_session):
    """GET /api/v1/inventory/products returns 200 with items, total, and required fields."""
    _seed_products(db_session, count=3)

    response = client.get("/api/v1/inventory/products")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 3
    assert len(data["items"]) == 3

    first = data["items"][0]
    assert first["sku_id"] == "SKU-000001"
    assert first["name"] == "Synthetic Product 1"
    assert first["category"] == "Hardware"
    assert first["unit_of_measure"] == "PCS"
    # Ensure no internal/sensitive fields are leaked
    assert "unit_cost" not in first
    assert "unit_price" not in first


# 2. Warehouses list
def test_get_warehouses_list_success(client, db_session):
    """GET /api/v1/inventory/warehouses returns 200 with items, total, and required fields."""
    _seed_warehouses(db_session, count=2)

    response = client.get("/api/v1/inventory/warehouses")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 2
    assert len(data["items"]) == 2

    first = data["items"][0]
    assert first["warehouse_id"] == "WH-BLR-01"
    assert first["name"] == "Bangalore Warehouse"
    assert first["city"] == "Bangalore"
    assert first["state"] == "Karnataka"
    assert first["country"] == "India"
    # Ensure internal fields are not leaked
    assert "capacity_units" not in first


# 3. Pagination
def test_products_pagination(client, db_session):
    """Pagination on products: limit=2 offset=0, limit=2 offset=2, total remains matching count."""
    _seed_products(db_session, count=5)

    # Page 1
    resp1 = client.get("/api/v1/inventory/products?limit=2&offset=0")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["total"] == 5
    assert len(data1["items"]) == 2
    assert data1["items"][0]["sku_id"] == "SKU-000001"
    assert data1["items"][1]["sku_id"] == "SKU-000002"

    # Page 2
    resp2 = client.get("/api/v1/inventory/products?limit=2&offset=2")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["total"] == 5
    assert len(data2["items"]) == 2
    assert data2["items"][0]["sku_id"] == "SKU-000003"
    assert data2["items"][1]["sku_id"] == "SKU-000004"


def test_warehouses_pagination(client, db_session):
    """Pagination on warehouses: limit=2 offset=0, limit=2 offset=2, total remains matching count."""
    _seed_warehouses(db_session, count=4)

    # Page 1
    resp1 = client.get("/api/v1/inventory/warehouses?limit=2&offset=0")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["total"] == 4
    assert len(data1["items"]) == 2

    # Page 2
    resp2 = client.get("/api/v1/inventory/warehouses?limit=2&offset=2")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["total"] == 4
    assert len(data2["items"]) == 2


# 4. IDs filter
def test_products_ids_filter(client, db_session):
    """Filter products by comma-separated canonical IDs, ignoring whitespace."""
    _seed_products(db_session, count=5)

    resp = client.get("/api/v1/inventory/products?ids=SKU-000001, SKU-000003")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    sku_ids = [item["sku_id"] for item in data["items"]]
    assert sku_ids == ["SKU-000001", "SKU-000003"]


def test_warehouses_ids_filter(client, db_session):
    """Filter warehouses by comma-separated canonical IDs."""
    _seed_warehouses(db_session, count=4)

    resp = client.get("/api/v1/inventory/warehouses?ids=WH-BLR-01,WH-BOM-01")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    wh_ids = [item["warehouse_id"] for item in data["items"]]
    assert "WH-BLR-01" in wh_ids
    assert "WH-BOM-01" in wh_ids


# 5. Unknown IDs
def test_products_unknown_ids(client, db_session):
    """Unknown IDs do not 404; unknown IDs are left out of items."""
    _seed_products(db_session, count=3)

    # Completely unknown ID
    resp_unknown = client.get("/api/v1/inventory/products?ids=SKU-NOT-EXIST")
    assert resp_unknown.status_code == 200
    data_unknown = resp_unknown.json()
    assert data_unknown["total"] == 0
    assert data_unknown["items"] == []

    # Mixed known and unknown IDs
    resp_mixed = client.get("/api/v1/inventory/products?ids=SKU-000001,SKU-NOT-EXIST")
    assert resp_mixed.status_code == 200
    data_mixed = resp_mixed.json()
    assert data_mixed["total"] == 1
    assert len(data_mixed["items"]) == 1
    assert data_mixed["items"][0]["sku_id"] == "SKU-000001"


def test_warehouses_unknown_ids(client, db_session):
    """Unknown warehouse IDs do not 404; unknown IDs are left out of items."""
    _seed_warehouses(db_session, count=2)

    resp_unknown = client.get("/api/v1/inventory/warehouses?ids=WH-NOT-EXIST")
    assert resp_unknown.status_code == 200
    data_unknown = resp_unknown.json()
    assert data_unknown["total"] == 0
    assert data_unknown["items"] == []

    resp_mixed = client.get("/api/v1/inventory/warehouses?ids=WH-BLR-01,WH-NOT-EXIST")
    assert resp_mixed.status_code == 200
    data_mixed = resp_mixed.json()
    assert data_mixed["total"] == 1
    assert len(data_mixed["items"]) == 1
    assert data_mixed["items"][0]["warehouse_id"] == "WH-BLR-01"


# 6. Empty table
def test_products_empty_table(client):
    """When products table is empty, returns items=[] and total=0."""
    resp = client.get("/api/v1/inventory/products")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_warehouses_empty_table(client):
    """When warehouses table is empty, returns items=[] and total=0."""
    resp = client.get("/api/v1/inventory/warehouses")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


# 7. Authentication / permission
def test_products_and_warehouses_require_permission(client):
    """User without inventory:read receives 403 Forbidden."""

    async def _procurement_override():
        return {
            "valid": True,
            "role": "procurement_manager",
            "user_id": 99,
            "permissions": ["supplier:read", "supplier:write"],
        }

    app.dependency_overrides[verify_token] = _procurement_override

    resp_prod = client.get("/api/v1/inventory/products")
    assert resp_prod.status_code == 403

    resp_wh = client.get("/api/v1/inventory/warehouses")
    assert resp_wh.status_code == 403


# 8. Route collision test
def test_route_collision_protection(client, db_session):
    """
    Prove GET /api/v1/inventory/products and GET /api/v1/inventory/warehouses
    reach their respective handlers and are NOT captured by /{sku_id}/{warehouse_id}.
    """
    _seed_products(db_session, count=1)
    _seed_warehouses(db_session, count=1)

    # 1. Product route reaches product handler (returns ProductListResponse with items/total)
    resp_prod = client.get("/api/v1/inventory/products")
    assert resp_prod.status_code == 200
    data_prod = resp_prod.json()
    assert "items" in data_prod
    assert "total" in data_prod

    # 2. Warehouse route reaches warehouse handler (returns WarehouseListResponse with items/total)
    resp_wh = client.get("/api/v1/inventory/warehouses")
    assert resp_wh.status_code == 200
    data_wh = resp_wh.json()
    assert "items" in data_wh
    assert "total" in data_wh

    # 3. An actual 2-segment inventory path reaches the inventory handler
    resp_inv = client.get("/api/v1/inventory/SKU-NONEXIST/WH-NONEXIST")
    assert resp_inv.status_code == 404
    assert resp_inv.json()["detail"] == "Inventory not found"


# 9. Extra Edge Cases
def test_pagination_validation_errors(client):
    """Verify limit and offset boundary validation rules."""
    # limit > 1000 is rejected with 422
    assert client.get("/api/v1/inventory/products?limit=1001").status_code == 422
    assert client.get("/api/v1/inventory/warehouses?limit=1001").status_code == 422

    # limit < 1 is rejected with 422
    assert client.get("/api/v1/inventory/products?limit=0").status_code == 422
    assert client.get("/api/v1/inventory/warehouses?limit=0").status_code == 422

    # offset < 0 is rejected with 422
    assert client.get("/api/v1/inventory/products?offset=-1").status_code == 422
    assert client.get("/api/v1/inventory/warehouses?offset=-1").status_code == 422


def test_product_nullable_unit_of_measure(client, db_session):
    """Product with null unit_of_measure safely serializes to null."""
    db_session.add(
        Product(
            sku_id="SKU-000099",
            name="Product Null UOM",
            category="Raw Materials",
            unit_of_measure=None,
            unit_cost=5.0,
            unit_price=8.0,
            is_active=True,
        )
    )
    db_session.commit()

    resp = client.get("/api/v1/inventory/products?ids=SKU-000099")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["unit_of_measure"] is None


def test_empty_string_ids_filter(client, db_session):
    """Empty or whitespace-only ids query parameter returns empty items without error."""
    _seed_products(db_session, count=2)
    _seed_warehouses(db_session, count=2)

    resp_prod_empty = client.get("/api/v1/inventory/products?ids=")
    assert resp_prod_empty.status_code == 200
    assert resp_prod_empty.json()["items"] == []
    assert resp_prod_empty.json()["total"] == 0

    resp_prod_spaces = client.get("/api/v1/inventory/products?ids=   ,   ")
    assert resp_prod_spaces.status_code == 200
    assert resp_prod_spaces.json()["items"] == []
    assert resp_prod_spaces.json()["total"] == 0

    resp_wh_empty = client.get("/api/v1/inventory/warehouses?ids=")
    assert resp_wh_empty.status_code == 200
    assert resp_wh_empty.json()["items"] == []
    assert resp_wh_empty.json()["total"] == 0

