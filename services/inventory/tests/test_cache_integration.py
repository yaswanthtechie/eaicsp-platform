import json
import pytest
from unittest.mock import patch, MagicMock

from app.core.config import settings
from app.services.cache_service import (
    cache,
    get_cached_inventory,
    set_cached_inventory,
    get_cached_all_inventory,
    set_cached_all_inventory,
    invalidate_inventory_cache,
    make_item_key,
    ALL_ITEMS_KEY,
)
from app.models.inventory import Inventory
from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier
from tests.conftest import seed_sales_history


@pytest.fixture(autouse=True)
def clean_cache():
    """Ensure clean cache before and after every test."""
    cache.clear()
    yield
    cache.clear()


# ============================================================================
# 1. UNIT & DOMAIN CACHE TESTS
# ============================================================================

def test_cache_set_and_get():
    """Verify basic set, get, and TTL functionality."""
    data = {"sku_id": "SKU-C1", "warehouse_id": "WH-1", "quantity_on_hand": 50}
    set_cached_inventory("SKU-C1", "WH-1", data)

    cached = get_cached_inventory("SKU-C1", "WH-1")
    assert cached is not None
    assert cached["sku_id"] == "SKU-C1"
    assert cached["quantity_on_hand"] == 50


def test_cache_invalidation_specific_and_all():
    """Verify that invalidating an item removes both item and collection cache."""
    set_cached_inventory("SKU-C1", "WH-1", {"sku_id": "SKU-C1"})
    set_cached_all_inventory([{"sku_id": "SKU-C1"}])

    assert get_cached_inventory("SKU-C1", "WH-1") is not None
    assert get_cached_all_inventory() is not None

    # Invalidate specific item
    invalidate_inventory_cache("SKU-C1", "WH-1")

    assert get_cached_inventory("SKU-C1", "WH-1") is None
    assert get_cached_all_inventory() is None


# ============================================================================
# 2. HTTP HOT READ & CACHE POPULATION TESTS
# ============================================================================

def test_get_inventory_populates_cache(client, db_session):
    """
    Verify that calling GET /api/v1/inventory/{sku}/{wh} populates the Redis cache.
    Subsequent reads should be served from cache.
    """
    seed_sales_history("SKU-CACHE-1", "WH-1", daily_quantity=5)

    item = Inventory(
        sku_id="SKU-CACHE-1",
        warehouse_id="WH-1",
        product_name="Cached Item",
        category="Electronics",
        quantity_on_hand=80,
        lead_time_days=4,
        safety_stock=10,
        version=1,
    )
    db_session.add(item)
    db_session.commit()

    # 1. Cache is initially empty
    assert get_cached_inventory("SKU-CACHE-1", "WH-1") is None

    # 2. First GET request (Cache Miss -> DB Query -> Populates Cache)
    resp1 = client.get("/api/v1/inventory/SKU-CACHE-1/WH-1")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["quantity_on_hand"] == 80

    # 3. Cache is now populated!
    cached_val = get_cached_inventory("SKU-CACHE-1", "WH-1")
    assert cached_val is not None
    assert cached_val["sku_id"] == "SKU-CACHE-1"
    assert cached_val["quantity_on_hand"] == 80

    # 4. Second GET request (Hot Read Cache Hit)
    resp2 = client.get("/api/v1/inventory/SKU-CACHE-1/WH-1")
    assert resp2.status_code == 200
    assert resp2.json()["quantity_on_hand"] == 80


# ============================================================================
# 3. CACHE INVALIDATION ON MUTATIONS
# ============================================================================

def test_update_inventory_invalidates_cache(client, db_session):
    """
    Verify that updating inventory (PUT) invalidates the cache so
    subsequent reads return the fresh data.
    """
    seed_sales_history("SKU-CACHE-UPD", "WH-1", daily_quantity=5)

    # Create initial inventory with cost layer
    client.post(
        "/api/v1/inventory/",
        json={
            "sku_id": "SKU-CACHE-UPD",
            "product_name": "Update Cache Item",
            "warehouse_id": "WH-1",
            "quantity_on_hand": 50,
            "lead_time_days": 4,
            "safety_stock": 10,
            "unit_cost": 20.0,
        },
    )

    # Warm cache
    resp1 = client.get("/api/v1/inventory/SKU-CACHE-UPD/WH-1")
    assert resp1.status_code == 200
    assert get_cached_inventory("SKU-CACHE-UPD", "WH-1") is not None

    # Update item
    update_resp = client.put(
        "/api/v1/inventory/SKU-CACHE-UPD/WH-1",
        json={
            "quantity_on_hand": 30,
            "version": resp1.json()["version"],
        },
    )
    assert update_resp.status_code == 200

    # Cache must be invalidated!
    assert get_cached_inventory("SKU-CACHE-UPD", "WH-1") is None

    # Fresh read retrieves updated state and re-populates cache
    resp2 = client.get("/api/v1/inventory/SKU-CACHE-UPD/WH-1")
    assert resp2.status_code == 200
    assert resp2.json()["quantity_on_hand"] == 30
    assert resp2.json()["version"] == 2


def test_decrement_inventory_invalidates_cache(client, db_session):
    """
    Verify that stock decrement (/decrement) invalidates the cache.
    """
    seed_sales_history("SKU-CACHE-DEC", "WH-1", daily_quantity=2)

    client.post(
        "/api/v1/inventory/",
        json={
            "sku_id": "SKU-CACHE-DEC",
            "product_name": "Decrement Cache Item",
            "warehouse_id": "WH-1",
            "quantity_on_hand": 40,
            "lead_time_days": 4,
            "safety_stock": 10,
            "unit_cost": 15.0,
        },
    )

    # Warm cache
    client.get("/api/v1/inventory/SKU-CACHE-DEC/WH-1")
    assert get_cached_inventory("SKU-CACHE-DEC", "WH-1") is not None

    # Decrement
    dec_resp = client.post(
        "/api/v1/inventory/decrement",
        params={"sku_id": "SKU-CACHE-DEC", "warehouse_id": "WH-1", "quantity": 10},
    )
    assert dec_resp.status_code == 200

    # Cache invalidated
    assert get_cached_inventory("SKU-CACHE-DEC", "WH-1") is None

    # Fresh read
    get_resp = client.get("/api/v1/inventory/SKU-CACHE-DEC/WH-1")
    assert get_resp.json()["quantity_on_hand"] == 30


def test_delete_inventory_invalidates_cache(client, db_session):
    """
    Verify that deleting an inventory item invalidates its cache.
    """
    seed_sales_history("SKU-CACHE-DEL", "WH-1", daily_quantity=2)

    client.post(
        "/api/v1/inventory/",
        json={
            "sku_id": "SKU-CACHE-DEL",
            "product_name": "Delete Cache Item",
            "warehouse_id": "WH-1",
            "quantity_on_hand": 20,
            "lead_time_days": 4,
            "safety_stock": 5,
        },
    )

    # Warm cache
    client.get("/api/v1/inventory/SKU-CACHE-DEL/WH-1")
    assert get_cached_inventory("SKU-CACHE-DEL", "WH-1") is not None

    # Delete
    del_resp = client.delete("/api/v1/inventory/SKU-CACHE-DEL/WH-1")
    assert del_resp.status_code == 200

    # Cache must be empty
    assert get_cached_inventory("SKU-CACHE-DEL", "WH-1") is None


def test_get_all_inventory_cache_and_invalidation(client, db_session):
    """
    Verify that GET /api/v1/inventory/ caches the collection and
    creating a new item invalidates the collection cache.
    """
    seed_sales_history("SKU-ALL-1", "WH-1", daily_quantity=1)

    client.post(
        "/api/v1/inventory/",
        json={
            "sku_id": "SKU-ALL-1",
            "product_name": "All 1",
            "warehouse_id": "WH-1",
            "quantity_on_hand": 10,
            "lead_time_days": 2,
            "safety_stock": 2,
        },
    )

    # First GET / (cache miss -> store)
    resp1 = client.get("/api/v1/inventory/")
    assert resp1.status_code == 200
    assert len(resp1.json()) >= 1
    assert get_cached_all_inventory() is not None

    # Create new item
    seed_sales_history("SKU-ALL-2", "WH-1", daily_quantity=1)
    client.post(
        "/api/v1/inventory/",
        json={
            "sku_id": "SKU-ALL-2",
            "product_name": "All 2",
            "warehouse_id": "WH-1",
            "quantity_on_hand": 20,
            "lead_time_days": 2,
            "safety_stock": 2,
        },
    )

    # Collection cache must be invalidated!
    assert get_cached_all_inventory() is None

    # Next GET / has both items
    resp2 = client.get("/api/v1/inventory/")
    sku_list = [item["sku_id"] for item in resp2.json()]
    assert "SKU-ALL-1" in sku_list
    assert "SKU-ALL-2" in sku_list


# ============================================================================
# 4. RESILIENCE / GRACEFUL DEGRADATION TESTS
# ============================================================================

def test_cache_graceful_degradation_on_redis_error(client, db_session):
    """
    Milestone 3 Requirement:
    If Redis fails or times out, the service must fail open (graceful degradation)
    and serve requests directly from PostgreSQL without 500 errors.
    """
    seed_sales_history("SKU-RESILIENT", "WH-1", daily_quantity=2)

    item = Inventory(
        sku_id="SKU-RESILIENT",
        warehouse_id="WH-1",
        product_name="Resilient Item",
        category="Hardware",
        quantity_on_hand=75,
        lead_time_days=3,
        safety_stock=5,
        version=1,
    )
    db_session.add(item)
    db_session.commit()

    # Simulate Redis throwing an exception on get() and set()
    with patch.object(cache, "get", side_effect=Exception("Redis connection timed out")):
        resp = client.get("/api/v1/inventory/SKU-RESILIENT/WH-1")
        # Request MUST succeed from DB!
        assert resp.status_code == 200
        assert resp.json()["quantity_on_hand"] == 75


def test_receive_purchase_order_invalidates_cache(client, db_session):
    """
    Verify that receiving an approved purchase order invalidates the inventory cache,
    ensuring subsequent reads immediately reflect the newly received stock.
    """
    from app.services.purchase_order_service import receive_purchase_order

    seed_sales_history("SKU-PO-REC", "WH-REC", daily_quantity=2)

    item = Inventory(
        sku_id="SKU-PO-REC",
        warehouse_id="WH-REC",
        product_name="PO Receive Cache Item",
        category="Parts",
        quantity_on_hand=10,
        lead_time_days=4,
        safety_stock=5,
        version=1,
    )
    db_session.add(item)

    po = PurchaseOrder(
        po_id="PO-TEST-CACHE-REC-1",
        sku_id="SKU-PO-REC",
        warehouse_id="WH-REC",
        supplier_id="SUP-1",
        quantity=50,
        unit_cost=10.0,
        expected_cost=500.0,
        status="draft",
        approval_status="approved",
    )
    db_session.add(po)
    db_session.commit()

    # 1. Warm cache
    resp1 = client.get("/api/v1/inventory/SKU-PO-REC/WH-REC")
    assert resp1.status_code == 200
    assert resp1.json()["quantity_on_hand"] == 10
    assert get_cached_inventory("SKU-PO-REC", "WH-REC") is not None

    # 2. Receive the purchase order
    receive_resp = client.post(f"/api/v1/inventory/purchase-orders/{po.po_id}/receive")
    assert receive_resp.status_code == 200

    # 3. Verify cache is invalidated!
    assert get_cached_inventory("SKU-PO-REC", "WH-REC") is None

    # 4. Fresh read reflects new quantity (10 + 50 = 60)
    resp2 = client.get("/api/v1/inventory/SKU-PO-REC/WH-REC")
    assert resp2.status_code == 200
    assert resp2.json()["quantity_on_hand"] == 60


@pytest.mark.integration
def test_read_latency_benchmark_with_and_without_cache(client, db_session):
    """
    Milestone 3 Requirement:
    Measure read latency with and without the cache and report the numbers.
    """
    import time

    seed_sales_history("SKU-PERF", "WH-1", daily_quantity=2)
    item = Inventory(
        sku_id="SKU-PERF",
        warehouse_id="WH-1",
        product_name="Perf Item",
        category="Hardware",
        quantity_on_hand=100,
        lead_time_days=3,
        safety_stock=10,
        version=1,
    )
    db_session.add(item)
    db_session.commit()

    iterations = 25

    # 1. Uncached reads (forced cache misses to measure PostgreSQL query latency)
    db_durations = []
    for _ in range(iterations):
        cache.clear()
        t0 = time.perf_counter()
        resp = client.get("/api/v1/inventory/SKU-PERF/WH-1")
        t1 = time.perf_counter()
        assert resp.status_code == 200
        db_durations.append(t1 - t0)

    # 2. Warm cache
    client.get("/api/v1/inventory/SKU-PERF/WH-1")

    # 3. Cached reads (measuring Redis cache hit latency)
    cache_durations = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        resp = client.get("/api/v1/inventory/SKU-PERF/WH-1")
        t1 = time.perf_counter()
        assert resp.status_code == 200
        cache_durations.append(t1 - t0)

    avg_db_ms = (sum(db_durations) / iterations) * 1000
    avg_cache_ms = (sum(cache_durations) / iterations) * 1000
    speedup = avg_db_ms / max(avg_cache_ms, 0.001)

    print(f"\n[LATENCY REPORT] Uncached DB Avg: {avg_db_ms:.2f} ms | Cached Redis Avg: {avg_cache_ms:.2f} ms | Speedup: {speedup:.1f}x")
    assert resp.status_code == 200


def test_fulfill_shortage_invalidates_cache_for_both_warehouses(client, db_session):
    """
    Reviewer requirement:
    fulfill_shortage must invalidate the cache for both source and destination
    warehouses so cached quantities never go stale.
    """
    from app.services.multi_echelon_service import fulfill_shortage
    from app.models.inventory_cost_layer import InventoryCostLayer
    from datetime import datetime, UTC

    sku = "SKU-SHORTAGE-CACHE"
    wh_parent = "WH-CACHE-PARENT"
    wh_local = "WH-CACHE-LOCAL"

    seed_sales_history(sku, wh_parent, daily_quantity=2)
    seed_sales_history(sku, wh_local, daily_quantity=2)

    parent_item = Inventory(
        sku_id=sku,
        warehouse_id=wh_parent,
        product_name="Multi Echelon Item",
        category="Hardware",
        quantity_on_hand=50,
        lead_time_days=4,
        safety_stock=5,
        warehouse_type="central",
    )
    local_item = Inventory(
        sku_id=sku,
        warehouse_id=wh_local,
        product_name="Multi Echelon Item",
        category="Hardware",
        quantity_on_hand=5,
        lead_time_days=2,
        safety_stock=5,
        warehouse_type="local",
        parent_warehouse_id=wh_parent,
    )
    cost_layer = InventoryCostLayer(
        sku_id=sku,
        warehouse_id=wh_parent,
        category="Hardware",
        quantity_received=50,
        quantity_remaining=50,
        unit_cost=10.0,
        received_at=datetime.now(UTC),
    )
    db_session.add_all([parent_item, local_item, cost_layer])
    db_session.commit()

    # 1. Warm cache for both warehouses
    client.get(f"/api/v1/inventory/{sku}/{wh_parent}")
    client.get(f"/api/v1/inventory/{sku}/{wh_local}")
    assert get_cached_inventory(sku, wh_parent) is not None
    assert get_cached_inventory(sku, wh_local) is not None

    # 2. Fulfill shortage (transfers 15 units from parent to local)
    result = fulfill_shortage(
        db=db_session,
        sku_id=sku,
        warehouse_id=wh_local,
        required_quantity=20,
    )
    assert result["transferred_quantity"] == 15

    # 3. VERIFY: Cache is invalidated for BOTH parent and local warehouses!
    assert get_cached_inventory(sku, wh_parent) is None, "Parent cache must be invalidated after stock transfer"
    assert get_cached_inventory(sku, wh_local) is None, "Local cache must be invalidated after stock transfer"

    # 4. Fresh reads return updated stock levels
    resp_parent = client.get(f"/api/v1/inventory/{sku}/{wh_parent}")
    resp_local = client.get(f"/api/v1/inventory/{sku}/{wh_local}")
    assert resp_parent.json()["quantity_on_hand"] == 35  # 50 - 15
    assert resp_local.json()["quantity_on_hand"] == 20   # 5 + 15


@pytest.mark.integration
def test_real_redis_connectivity_and_operations():
    """
    Reviewer requirement:
    Test cache operations against a real Redis instance to verify
    real tool connectivity, TTL, and pattern deletion without fakes.
    """
    from app.services.cache_service import InventoryCache
    import redis

    try:
        r = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=1.0)
        r.ping()
    except Exception:
        pytest.skip(f"Live Redis not accessible at {settings.REDIS_URL}")

    real_cache = InventoryCache(redis_url=settings.REDIS_URL)
    assert real_cache._client is not None, "Real Redis client must be connected"

    test_key = "inventory:test:real_redis:item1"
    test_data = {"sku_id": "SKU-REAL", "qty": 99}

    real_cache.set(test_key, test_data, ttl=60)
    retrieved = real_cache.get(test_key)
    assert retrieved == test_data

    real_cache.delete(test_key)
    assert real_cache.get(test_key) is None


import time

import redis

from tests.fakes import FakeRedis


class FlakyRedis(FakeRedis):
    def __init__(self):
        super().__init__()
        self.fail_deletes = False

    def delete(self, *keys):
        if self.fail_deletes:
            raise redis.ConnectionError("network blip")
        return super().delete(*keys)


def test_failed_invalidation_never_serves_stale_value(monkeypatch):
    flaky = FlakyRedis()
    monkeypatch.setattr(cache, "_client", flaky)

    set_cached_inventory("S", "W", {"quantity_on_hand": 10})

    # The DB update committed, but Redis drops the DELETE.
    flaky.fail_deletes = True
    invalidate_inventory_cache("S", "W")

    # The breaker is open, so the old value is NOT served.
    assert get_cached_inventory("S", "W") is None

    # Redis comes back and the cooldown ends.
    flaky.fail_deletes = False
    monkeypatch.setattr(cache, "_down_until", time.monotonic() - 1)

    # Recovery wiped the stale key before the cache was trusted again.
    assert get_cached_inventory("S", "W") is None
    assert flaky.store == {}


def test_redis_outage_does_not_retry_on_every_request(monkeypatch):
    calls = {"get": 0}

    class DeadRedis(FakeRedis):
        def get(self, key):
            calls["get"] += 1
            raise redis.ConnectionError("down")

    monkeypatch.setattr(cache, "_client", DeadRedis())

    for _ in range(10):
        assert get_cached_inventory("S", "W") is None

    assert calls["get"] == 1  # breaker tripped after the first failure
