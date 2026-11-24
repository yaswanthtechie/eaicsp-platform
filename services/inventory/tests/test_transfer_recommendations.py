import json
from pathlib import Path

from fastapi.testclient import TestClient
from jsonschema import validate as jsonschema_validate

from app.core.auth import verify_token
from app.core.config import settings
from app.database import get_db
from app.main import app
from app.models.inventory import Inventory
from app.models.outbox import Outbox
from app.models.product import Product
from app.models.supplier import Supplier
from app.services.transfer_recommendation_service import (
    calculate_stock_cover,
    find_configured_lane,
    generate_transfer_recommendations,
)
from tests.conftest import ROLE_PERMISSIONS, override_get_db, seed_sales_history

REPO_ROOT = Path(__file__).resolve().parents[3]


# ============================================================
# 1. UNIT TESTS: LANE LOOKUP & STOCK COVER
# ============================================================


def test_find_configured_lane():
    """Verify configured lane lookup and handling of missing lanes."""
    test_lanes = [
        {
            "from_warehouse": "WH-BLR-01",
            "to_warehouse": "WH-BOM-01",
            "lead_time_days": 2,
            "cost_per_unit": 4.5,
        },
        {
            "from": "WH-DEL-01",
            "to": "WH-BLR-01",
            "lead_time_days": 3,
            "cost_per_unit": 6.0,
        },
    ]

    lane1 = find_configured_lane("WH-BLR-01", "WH-BOM-01", lanes=test_lanes)
    assert lane1 is not None
    assert lane1["lead_time_days"] == 2
    assert lane1["cost_per_unit"] == 4.5

    lane2 = find_configured_lane("WH-DEL-01", "WH-BLR-01", lanes=test_lanes)
    assert lane2 is not None
    assert lane2["lead_time_days"] == 3
    assert lane2["cost_per_unit"] == 6.0

    # Missing lane returns None
    assert find_configured_lane("WH-BLR-01", "WH-DEL-01", lanes=test_lanes) is None


def test_calculate_stock_cover():
    """Verify stock cover calculations for positive demand and zero demand."""
    # Positive demand: 100 units / 2 units/day = 50 days (above 30 days)
    cover_days, has_excess, reserve = calculate_stock_cover(
        quantity_on_hand=100, avg_daily_demand=2.0
    )
    assert cover_days == 50.0
    assert has_excess is True
    assert reserve == 60  # 2.0 * 30 days

    # Positive demand below threshold: 40 units / 2 units/day = 20 days (below 30 days)
    cover_days, has_excess, reserve = calculate_stock_cover(
        quantity_on_hand=40, avg_daily_demand=2.0
    )
    assert cover_days == 20.0
    assert has_excess is False

    # Zero demand: positive stock has infinite cover (dormant stock)
    cover_days, has_excess, reserve = calculate_stock_cover(
        quantity_on_hand=50, avg_daily_demand=0.0
    )
    assert cover_days == float("inf")
    assert has_excess is True
    assert reserve == 0

    # Zero demand and 0 stock: 0 cover
    cover_days, has_excess, reserve = calculate_stock_cover(
        quantity_on_hand=0, avg_daily_demand=0.0
    )
    assert cover_days == 0.0
    assert has_excess is False


# ============================================================
# 2. CORE DECISION LOGIC TESTS
# ============================================================


def test_transfer_chosen_when_faster_and_cheaper(db_session, monkeypatch):
    """
    Test 1: Transfer chosen when lane lead time < PO lead time and
    transfer cost < configured share of PO cost.
    """
    sku_id = "SKU-000101"
    wh_dest = "WH-BLR-01"
    wh_source = "WH-BOM-01"

    # Configure custom lane: BOM -> BLR in 2 days at 5.0 cost/unit
    monkeypatch.setattr(
        settings,
        "TRANSFER_LANES",
        [
            {
                "from_warehouse": wh_source,
                "to_warehouse": wh_dest,
                "lead_time_days": 2,
                "cost_per_unit": 5.0,
            }
        ],
    )
    monkeypatch.setattr(settings, "TRANSFER_EXCESS_STOCK_COVER_DAYS", 30)
    monkeypatch.setattr(settings, "TRANSFER_MAX_PO_COST_SHARE", 0.50)

    # Destination: ROP = 50, QOH = 10 -> shortage = 40. PO lead time = 8 days.
    db_session.add(
        Inventory(
            sku_id=sku_id,
            warehouse_id=wh_dest,
            product_name="Transfer Item",
            category="Industrial",
            quantity_on_hand=10,
            lead_time_days=8,
            safety_stock=20,
            reorder_point=50,
            warehouse_type="local",
        )
    )

    # Source: QOH = 200, ROP = 30. Avg demand = 2 units/day -> cover = 100 days.
    # Reserve for 30d cover = 60. Max(ROP 30, Reserve 60) = 60. Excess = 140.
    db_session.add(
        Inventory(
            sku_id=sku_id,
            warehouse_id=wh_source,
            product_name="Transfer Item",
            category="Industrial",
            quantity_on_hand=200,
            lead_time_days=5,
            safety_stock=15,
            reorder_point=30,
            warehouse_type="local",
        )
    )
    seed_sales_history(sku_id=sku_id, warehouse_id=wh_source, daily_quantity=2, days=30)

    # Supplier: unit cost = 50.0 -> PO cost for 40 units = 2000.0.
    # Transfer cost for 40 units @ 5.0 = 200.0 (10% of PO cost, < 50% max).
    db_session.add(
        Supplier(
            supplier_id="SUP-00011",
            supplier_name="Alpha Supplies",
            sku_id=sku_id,
            unit_cost=50.0,
            lead_time_days=8,
        )
    )
    db_session.commit()

    recs = generate_transfer_recommendations(db=db_session, publish_events=True)

    dest_rec = next((r for r in recs if r["destination_warehouse_id"] == wh_dest), None)
    assert dest_rec is not None
    assert dest_rec["recommendation"] == "TRANSFER"
    assert dest_rec["source_warehouse_id"] == wh_source
    assert dest_rec["recommended_quantity"] == 40
    assert dest_rec["days_saved"] == 6  # 8 - 2 days
    assert dest_rec["estimated_cost_savings"] == 1800.0  # 2000 - 200
    assert "Transfer from WH-BOM-01 arrives 6 days faster" in dest_rec["reason"]
    assert dest_rec["numbers"]["transfer_cost"] == 200.0
    assert dest_rec["numbers"]["po_cost"] == 2000.0


def test_po_chosen_when_transfer_is_slower(db_session, monkeypatch):
    """
    Test 2: PO chosen when transfer lane is slower or equal to PO lead time.
    """
    sku_id = "SKU-000102"
    wh_dest = "WH-BLR-01"
    wh_source = "WH-BOM-01"

    # Configure lane: BOM -> BLR in 10 days (slower than PO lead time of 6 days)
    monkeypatch.setattr(
        settings,
        "TRANSFER_LANES",
        [
            {
                "from_warehouse": wh_source,
                "to_warehouse": wh_dest,
                "lead_time_days": 10,
                "cost_per_unit": 2.0,
            }
        ],
    )

    db_session.add(
        Inventory(
            sku_id=sku_id,
            warehouse_id=wh_dest,
            product_name="Slow Lane Item",
            category="Industrial",
            quantity_on_hand=5,
            lead_time_days=6,
            safety_stock=10,
            reorder_point=30,
            warehouse_type="local",
        )
    )
    db_session.add(
        Inventory(
            sku_id=sku_id,
            warehouse_id=wh_source,
            product_name="Slow Lane Item",
            category="Industrial",
            quantity_on_hand=150,
            lead_time_days=5,
            safety_stock=10,
            reorder_point=20,
            warehouse_type="local",
        )
    )
    seed_sales_history(sku_id=sku_id, warehouse_id=wh_source, daily_quantity=1, days=30)
    db_session.add(
        Supplier(
            supplier_id="SUP-00012",
            supplier_name="Beta Supplies",
            sku_id=sku_id,
            unit_cost=60.0,
            lead_time_days=6,
        )
    )
    db_session.commit()

    recs = generate_transfer_recommendations(db=db_session, publish_events=False)
    dest_rec = next((r for r in recs if r["destination_warehouse_id"] == wh_dest), None)

    assert dest_rec is not None
    assert dest_rec["recommendation"] == "PURCHASE_ORDER"
    assert dest_rec["source_warehouse_id"] is None
    assert dest_rec["recommended_quantity"] == 25  # ROP 30 - QOH 5
    assert "not faster than PO" in dest_rec["reason"]


def test_source_warehouse_protected_below_reorder_point(db_session, monkeypatch):
    """
    Test 3: Never take the source warehouse below its own reorder point.
    Transfer quantity is capped so source quantity does not drop below source ROP.
    """
    sku_id = "SKU-000103"
    wh_dest = "WH-BLR-01"
    wh_source = "WH-BOM-01"

    monkeypatch.setattr(
        settings,
        "TRANSFER_LANES",
        [
            {
                "from_warehouse": wh_source,
                "to_warehouse": wh_dest,
                "lead_time_days": 2,
                "cost_per_unit": 3.0,
            }
        ],
    )
    monkeypatch.setattr(settings, "TRANSFER_EXCESS_STOCK_COVER_DAYS", 10)

    # Destination shortage = 50 - 10 = 40 units
    db_session.add(
        Inventory(
            sku_id=sku_id,
            warehouse_id=wh_dest,
            product_name="Protected Source Item",
            category="Industrial",
            quantity_on_hand=10,
            lead_time_days=7,
            safety_stock=20,
            reorder_point=50,
            warehouse_type="local",
        )
    )

    # Source: QOH = 65, ROP = 50. Avg demand = 1 unit/day -> cover = 65 days (> 10d).
    # Reserve for 10d cover = 10 units.
    # Source minimum required = max(ROP 50, Reserve 10) = 50.
    # Available excess = 65 - 50 = 15 units.
    db_session.add(
        Inventory(
            sku_id=sku_id,
            warehouse_id=wh_source,
            product_name="Protected Source Item",
            category="Industrial",
            quantity_on_hand=65,
            lead_time_days=5,
            safety_stock=20,
            reorder_point=50,
            warehouse_type="local",
        )
    )
    seed_sales_history(sku_id=sku_id, warehouse_id=wh_source, daily_quantity=1, days=30)
    db_session.add(
        Supplier(
            supplier_id="SUP-00013",
            supplier_name="Gamma Supplies",
            sku_id=sku_id,
            unit_cost=80.0,
            lead_time_days=7,
        )
    )
    db_session.commit()

    recs = generate_transfer_recommendations(db=db_session, publish_events=False)
    dest_rec = next((r for r in recs if r["destination_warehouse_id"] == wh_dest), None)

    assert dest_rec is not None
    assert dest_rec["recommendation"] == "TRANSFER"
    # Even though destination shortage is 40, transfer is capped at 15 to protect source ROP!
    assert dest_rec["recommended_quantity"] == 15
    assert dest_rec["numbers"]["source_excess_quantity"] == 15
    # Source remaining after transfer: 65 - 15 = 50 == source_reorder_point
    assert (
        dest_rec["numbers"]["source_quantity_on_hand"]
        - dest_rec["recommended_quantity"]
        >= dest_rec["numbers"]["source_reorder_point"]
    )


def test_no_lane_gives_no_transfer(db_session, monkeypatch):
    """
    Test 4: Warehouses have excess stock, but no configured transfer lane exists.
    Must recommend PO instead.
    """
    sku_id = "SKU-000104"
    wh_dest = "WH-BLR-01"
    wh_source = "WH-DEL-01"

    # Only configure an unrelated lane (BOM -> MAA)
    monkeypatch.setattr(
        settings,
        "TRANSFER_LANES",
        [
            {
                "from_warehouse": "WH-BOM-01",
                "to_warehouse": "WH-MAA-01",
                "lead_time_days": 2,
                "cost_per_unit": 5.0,
            }
        ],
    )

    db_session.add(
        Inventory(
            sku_id=sku_id,
            warehouse_id=wh_dest,
            product_name="Unconnected Lane Item",
            category="Industrial",
            quantity_on_hand=5,
            lead_time_days=7,
            safety_stock=10,
            reorder_point=30,
            warehouse_type="local",
        )
    )
    db_session.add(
        Inventory(
            sku_id=sku_id,
            warehouse_id=wh_source,
            product_name="Unconnected Lane Item",
            category="Industrial",
            quantity_on_hand=200,
            lead_time_days=4,
            safety_stock=10,
            reorder_point=20,
            warehouse_type="local",
        )
    )
    seed_sales_history(sku_id=sku_id, warehouse_id=wh_source, daily_quantity=1, days=30)
    db_session.add(
        Supplier(
            supplier_id="SUP-00014",
            supplier_name="Delta Supplies",
            sku_id=sku_id,
            unit_cost=40.0,
            lead_time_days=7,
        )
    )
    db_session.commit()

    recs = generate_transfer_recommendations(db=db_session, publish_events=False)
    dest_rec = next((r for r in recs if r["destination_warehouse_id"] == wh_dest), None)

    assert dest_rec is not None
    assert dest_rec["recommendation"] == "PURCHASE_ORDER"
    assert "no configured transfer lane" in dest_rec["reason"]


def test_po_chosen_when_transfer_cost_exceeds_threshold(db_session, monkeypatch):
    """
    Test 5: Transfer arrives faster, but transit cost exceeds the configured share of PO cost.
    Must recommend PO instead.
    """
    sku_id = "SKU-000105"
    wh_dest = "WH-BLR-01"
    wh_source = "WH-BOM-01"

    # Transfer cost = 40.0/unit, while PO unit cost is only 50.0.
    # Cost share = 40/50 = 80%, exceeding configured max of 50%.
    monkeypatch.setattr(
        settings,
        "TRANSFER_LANES",
        [
            {
                "from_warehouse": wh_source,
                "to_warehouse": wh_dest,
                "lead_time_days": 2,
                "cost_per_unit": 40.0,
            }
        ],
    )
    monkeypatch.setattr(settings, "TRANSFER_MAX_PO_COST_SHARE", 0.50)

    db_session.add(
        Inventory(
            sku_id=sku_id,
            warehouse_id=wh_dest,
            product_name="Expensive Transit Item",
            category="Industrial",
            quantity_on_hand=5,
            lead_time_days=8,
            safety_stock=10,
            reorder_point=25,
            warehouse_type="local",
        )
    )
    db_session.add(
        Inventory(
            sku_id=sku_id,
            warehouse_id=wh_source,
            product_name="Expensive Transit Item",
            category="Industrial",
            quantity_on_hand=150,
            lead_time_days=4,
            safety_stock=10,
            reorder_point=20,
            warehouse_type="local",
        )
    )
    seed_sales_history(sku_id=sku_id, warehouse_id=wh_source, daily_quantity=1, days=30)
    db_session.add(
        Supplier(
            supplier_id="SUP-00015",
            supplier_name="Epsilon Supplies",
            sku_id=sku_id,
            unit_cost=50.0,
            lead_time_days=8,
        )
    )
    db_session.commit()

    recs = generate_transfer_recommendations(db=db_session, publish_events=False)
    dest_rec = next((r for r in recs if r["destination_warehouse_id"] == wh_dest), None)

    assert dest_rec is not None
    assert dest_rec["recommendation"] == "PURCHASE_ORDER"
    assert "not less than 50% of PO cost" in dest_rec["reason"]


# ============================================================
# 3. OUTBOX EVENT & CONTRACT COMPLIANCE TESTS
# ============================================================


def test_transfer_recommended_event_matches_contract(db_session, monkeypatch):
    """
    Test 6: Emitted event in outbox matches contracts/events/inventory.transfer.recommended.v1.json.
    """
    sku_id = "SKU-000106"
    wh_dest = "WH-BLR-01"
    wh_source = "WH-BOM-01"

    monkeypatch.setattr(
        settings,
        "TRANSFER_LANES",
        [
            {
                "from_warehouse": wh_source,
                "to_warehouse": wh_dest,
                "lead_time_days": 2,
                "cost_per_unit": 4.0,
            }
        ],
    )

    db_session.add(
        Inventory(
            sku_id=sku_id,
            warehouse_id=wh_dest,
            product_name="Event Test Item",
            category="Industrial",
            quantity_on_hand=10,
            lead_time_days=7,
            safety_stock=15,
            reorder_point=40,
            warehouse_type="local",
        )
    )
    db_session.add(
        Inventory(
            sku_id=sku_id,
            warehouse_id=wh_source,
            product_name="Event Test Item",
            category="Industrial",
            quantity_on_hand=100,
            lead_time_days=4,
            safety_stock=10,
            reorder_point=20,
            warehouse_type="local",
        )
    )
    seed_sales_history(sku_id=sku_id, warehouse_id=wh_source, daily_quantity=1, days=30)
    db_session.add(
        Supplier(
            supplier_id="SUP-00016",
            supplier_name="Zeta Supplies",
            sku_id=sku_id,
            unit_cost=60.0,
            lead_time_days=7,
        )
    )
    db_session.commit()

    # Generate recommendations with event publishing enabled
    generate_transfer_recommendations(db=db_session, publish_events=True)

    # Check outbox for the event
    outbox_entry = (
        db_session.query(Outbox)
        .filter(Outbox.event_type == "inventory.transfer.recommended")
        .first()
    )
    assert outbox_entry is not None
    assert outbox_entry.status == "PENDING"

    # Validate against JSON schema
    schema_path = (
        REPO_ROOT / "contracts" / "events" / "inventory.transfer.recommended.v1.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    envelope = json.loads(outbox_entry.payload)
    jsonschema_validate(instance=envelope, schema=schema)

    # Verify key payload fields
    payload = envelope["payload"]
    assert payload["sku_id"] == sku_id
    assert payload["source_warehouse_id"] == wh_source
    assert payload["destination_warehouse_id"] == wh_dest
    assert payload["transfer_quantity"] == 30
    assert payload["transfer_lead_time_days"] == 2
    assert payload["po_lead_time_days"] == 7


# ============================================================
# 4. API ENDPOINT & PERMISSIONS TESTS
# ============================================================


def test_transfer_recommendations_api_endpoint(client, db_session, monkeypatch):
    """
    Test 7: Verify GET /api/v1/inventory/transfer-recommendations endpoint returns 200
    with formatted schema.
    """
    sku_id = "SKU-000107"
    wh_dest = "WH-BLR-01"
    wh_source = "WH-BOM-01"

    monkeypatch.setattr(
        settings,
        "TRANSFER_LANES",
        [
            {
                "from_warehouse": wh_source,
                "to_warehouse": wh_dest,
                "lead_time_days": 2,
                "cost_per_unit": 5.0,
            }
        ],
    )

    db_session.add(
        Product(
            sku_id=sku_id,
            name="API Test Item",
            category="Industrial",
            unit_price=100.0,
            unit_cost=50.0,
        )
    )
    db_session.add(
        Inventory(
            sku_id=sku_id,
            warehouse_id=wh_dest,
            product_name="API Test Item",
            category="Industrial",
            quantity_on_hand=10,
            lead_time_days=6,
            safety_stock=10,
            reorder_point=30,
            warehouse_type="local",
        )
    )
    db_session.add(
        Inventory(
            sku_id=sku_id,
            warehouse_id=wh_source,
            product_name="API Test Item",
            category="Industrial",
            quantity_on_hand=120,
            lead_time_days=4,
            safety_stock=10,
            reorder_point=20,
            warehouse_type="local",
        )
    )
    seed_sales_history(sku_id=sku_id, warehouse_id=wh_source, daily_quantity=1, days=30)
    db_session.commit()

    res = client.get(
        "/api/v1/inventory/transfer-recommendations",
        headers={"Authorization": "Bearer warehouse-token"},
    )
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    item = next((x for x in data if x["destination_warehouse_id"] == wh_dest), None)
    assert item is not None
    assert item["sku_id"] == sku_id
    assert item["recommendation"] == "TRANSFER"
    assert "numbers" in item
    assert item["numbers"]["shortage_quantity"] == 20


def test_transfer_recommendations_api_permissions(db_session):
    """
    Test 8: Verify authentication & permissions for transfer-recommendations:
    - Missing token -> 401
    - Supplier role (lacks inventory:read) -> 403
    - Procurement manager / Warehouse manager (has inventory:read) -> 200
    """
    app.dependency_overrides[get_db] = override_get_db

    # 1. Anonymous -> 401
    with TestClient(app) as anon_client:
        res = anon_client.get("/api/v1/inventory/transfer-recommendations")
        assert res.status_code == 401

    # 2. Supplier (lacks inventory:read) -> 403
    async def _supplier_override():
        return {
            "valid": True,
            "role": "supplier",
            "user_id": 88,
            "permissions": ROLE_PERMISSIONS["supplier"],
        }

    app.dependency_overrides[verify_token] = _supplier_override
    with TestClient(app) as sup_client:
        res = sup_client.get(
            "/api/v1/inventory/transfer-recommendations",
            headers={"Authorization": "Bearer supplier-token"},
        )
        assert res.status_code == 403

    # 3. Procurement Manager (has inventory:read) -> 200
    async def _procurement_override():
        return {
            "valid": True,
            "role": "procurement_manager",
            "user_id": 99,
            "permissions": ROLE_PERMISSIONS["procurement_manager"],
        }

    app.dependency_overrides[verify_token] = _procurement_override
    with TestClient(app) as pm_client:
        res = pm_client.get(
            "/api/v1/inventory/transfer-recommendations",
            headers={"Authorization": "Bearer pm-token"},
        )
        assert res.status_code == 200

    app.dependency_overrides.clear()
