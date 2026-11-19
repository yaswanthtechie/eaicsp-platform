"""Production-grade deterministic tests for Client Data Readiness (Issue #325).

Covers:
1. Inventory snapshot import with provided vs calculated fallback values (ROP & safety stock).
2. Purchase order history import with Open, Received, and Cancelled statuses and date validation.
3. Supplier on-time delivery % (Received-only denominator, on_time <= expected_date,
   Open and Cancelled POs completely ignored, zero-division safe).
4. API endpoints:
   - GET /api/v1/inventory/suppliers/performance
   - GET /api/v1/inventory/suppliers/{supplier_id}/performance
5. End-to-end integration proving existing reorder recommendation logic works on client data.
"""

from __future__ import annotations

import csv
from datetime import date

import pytest

from app.models.inventory import Inventory
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier, SupplierLeadTime
from app.models.warehouse import Warehouse
from app.services.client_import_service import (
    ClientImportValidationError,
    StagingDataset,
    import_staging_dataset,
    run_client_data_import,
)
from app.services.reorder_service import (
    calculate_reorder_point,
)
from app.services.supplier_performance_service import (
    get_supplier_performance,
)


def _seed_master_data(db) -> None:
    """Seed minimal canonical master entities required for foreign keys."""
    # Suppliers
    sup1 = Supplier(
        supplier_id="SUP-00001",
        supplier_name="Alpha Tech Components",
        lead_time_days=7,
        unit_cost=50.0,
        sku_id="SKU-000001",
    )
    sup2 = Supplier(
        supplier_id="SUP-00002",
        supplier_name="Beta Logistics Supply",
        lead_time_days=10,
        unit_cost=80.0,
        sku_id="SKU-000002",
    )
    db.add_all([sup1, sup2])

    # Products
    p1 = Product(
        sku_id="SKU-000001",
        name="Micro Controller Unit",
        category="Hardware",
        unit_of_measure="PCS",
        unit_cost=50.0,
        unit_price=75.0,
        is_active=True,
    )
    p2 = Product(
        sku_id="SKU-000002",
        name="Optical Sensor Module",
        category="Electronics",
        unit_of_measure="PCS",
        unit_cost=80.0,
        unit_price=120.0,
        is_active=True,
    )
    db.add_all([p1, p2])

    # Warehouses
    w1 = Warehouse(
        warehouse_id="WH-BLR-01",
        name="Bengaluru Central DC",
        city="Bengaluru",
        state="Karnataka",
        country="India",
        pincode="560001",
        warehouse_type="regional",
        capacity_units=10000,
    )
    w2 = Warehouse(
        warehouse_id="WH-BOM-01",
        name="Mumbai Hub",
        city="Mumbai",
        state="Maharashtra",
        country="India",
        pincode="400001",
        warehouse_type="regional",
        capacity_units=10000,
    )
    db.add_all([w1, w2])

    # Supplier lead times
    lt1 = SupplierLeadTime(
        supplier_id="SUP-00001",
        sku_id="SKU-000001",
        average_lead_time_days=7,
        minimum_lead_time_days=5,
        maximum_lead_time_days=10,
        effective_date=date(2026, 1, 1),
    )
    lt2 = SupplierLeadTime(
        supplier_id="SUP-00002",
        sku_id="SKU-000002",
        average_lead_time_days=10,
        minimum_lead_time_days=7,
        maximum_lead_time_days=14,
        effective_date=date(2026, 1, 1),
    )
    db.add_all([lt1, lt2])
    db.commit()


# =========================================================================
# 1. INVENTORY SNAPSHOT IMPORT TESTS
# =========================================================================


def test_inventory_snapshot_provided_rop_and_safety_stock(db_session):
    """When snapshot provides ROP and safety_stock, they are imported directly."""
    _seed_master_data(db_session)

    dataset = StagingDataset(
        inventory_snapshots=[
            {
                "sku_id": "SKU-000001",
                "warehouse_id": "WH-BLR-01",
                "quantity_on_hand": "15",
                "reorder_point": "30",
                "safety_stock": "10",
                "snapshot_date": "2026-11-10",
            }
        ]
    )

    summary = import_staging_dataset(db_session, dataset, dry_run=False)
    assert summary.inventory_snapshots.added == 1
    assert len(summary.snapshot_records) == 1

    rec = summary.snapshot_records[0]
    assert rec.sku_id == "SKU-000001"
    assert rec.quantity_on_hand == 15
    assert rec.reorder_point == 30
    assert rec.reorder_point_source == "imported"
    assert rec.safety_stock == 10
    assert rec.safety_stock_source == "imported"
    assert rec.fallback_reason is None

    # Check database persistence
    inv = (
        db_session.query(Inventory)
        .filter_by(sku_id="SKU-000001", warehouse_id="WH-BLR-01")
        .first()
    )
    assert inv is not None
    assert inv.quantity_on_hand == 15
    assert inv.reorder_point == 30
    assert inv.safety_stock == 10


def test_inventory_snapshot_missing_rop_and_safety_stock_fallback(db_session):
    """When snapshot omits ROP and safety stock, fallback calculation is used and recorded."""
    _seed_master_data(db_session)

    # Empty string or omitted fields trigger fallback
    dataset = StagingDataset(
        inventory_snapshots=[
            {
                "sku_id": "SKU-000002",
                "warehouse_id": "WH-BOM-01",
                "quantity_on_hand": "45",
                "reorder_point": "",  # missing
                "safety_stock": "",  # missing
                "snapshot_date": "2026-11-10",
            }
        ]
    )

    summary = import_staging_dataset(db_session, dataset, dry_run=False)
    assert summary.inventory_snapshots.added == 1
    assert len(summary.snapshot_records) == 1

    rec = summary.snapshot_records[0]
    assert rec.sku_id == "SKU-000002"
    assert rec.quantity_on_hand == 45
    assert rec.reorder_point_source == "calculated"
    assert rec.safety_stock_source == "default"
    assert rec.fallback_reason == "missing from client snapshot"
    assert rec.reorder_point >= 0
    assert rec.safety_stock >= 0

    inv = (
        db_session.query(Inventory)
        .filter_by(sku_id="SKU-000002", warehouse_id="WH-BOM-01")
        .first()
    )
    assert inv is not None
    assert inv.quantity_on_hand == 45
    # A calculated reorder point is not stored, so it keeps recalculating.
    assert inv.reorder_point is None
    assert inv.safety_stock == rec.safety_stock


def test_inventory_snapshot_client_codes_without_canonical_ids_are_rejected(db_session):
    """Mapping client codes is the #323 loader's job; Inventory needs canonical IDs."""
    _seed_master_data(db_session)
    dataset = StagingDataset(
        inventory_snapshots=[
            {
                "product_code": "PRD-10482",
                "warehouse_code": "HYD-01",
                "quantity_on_hand": "120",
                "reorder_point": "50",
                "safety_stock": "20",
            }
        ]
    )
    with pytest.raises(
        ClientImportValidationError, match="missing required field 'sku_id'"
    ):
        import_staging_dataset(db_session, dataset, dry_run=False)


def test_calculated_reorder_point_keeps_recalculating(db_session):
    """A fallback reorder point must follow later changes, not stay frozen."""
    _seed_master_data(db_session)
    dataset = StagingDataset(
        inventory_snapshots=[
            {
                "sku_id": "SKU-000002",
                "warehouse_id": "WH-BOM-01",
                "quantity_on_hand": "45",
                "reorder_point": "",
                "safety_stock": "",
            }
        ]
    )
    import_staging_dataset(db_session, dataset, dry_run=False)
    inv = (
        db_session.query(Inventory)
        .filter_by(sku_id="SKU-000002", warehouse_id="WH-BOM-01")
        .one()
    )
    before = calculate_reorder_point(db_session, inv)["reorder_point"]
    inv.safety_stock += 500
    db_session.commit()
    assert calculate_reorder_point(db_session, inv)["reorder_point"] > before


def test_inventory_snapshot_duplicate_key_rejected(db_session):
    """Duplicate (sku_id, warehouse_id) in the same snapshot batch raises validation error."""
    _seed_master_data(db_session)
    dataset = StagingDataset(
        inventory_snapshots=[
            {
                "sku_id": "SKU-000001",
                "warehouse_id": "WH-BLR-01",
                "quantity_on_hand": "10",
            },
            {
                "sku_id": "SKU-000001",
                "warehouse_id": "WH-BLR-01",
                "quantity_on_hand": "20",
            },
        ]
    )
    with pytest.raises(ClientImportValidationError, match="duplicate canonical key"):
        import_staging_dataset(db_session, dataset)


def test_inventory_snapshot_unknown_sku_or_warehouse_rejected(db_session):
    """Foreign key violations in snapshots fail cleanly with clear message and zero writes."""
    _seed_master_data(db_session)
    bad_sku = StagingDataset(
        inventory_snapshots=[
            {
                "sku_id": "SKU-999999",
                "warehouse_id": "WH-BLR-01",
                "quantity_on_hand": "10",
            }
        ]
    )
    with pytest.raises(
        ClientImportValidationError, match="unknown sku_id 'SKU-999999'"
    ):
        import_staging_dataset(db_session, bad_sku)

    bad_wh = StagingDataset(
        inventory_snapshots=[
            {
                "sku_id": "SKU-000001",
                "warehouse_id": "WH-DEL-01",
                "quantity_on_hand": "10",
            }
        ]
    )
    with pytest.raises(
        ClientImportValidationError, match="unknown warehouse_id 'WH-DEL-01'"
    ):
        import_staging_dataset(db_session, bad_wh)


# =========================================================================
# 2. PURCHASE ORDER HISTORY IMPORT TESTS
# =========================================================================


def test_purchase_order_history_statuses(db_session):
    """PO history loads Open, Received, and Cancelled POs correctly."""
    _seed_master_data(db_session)

    dataset = StagingDataset(
        purchase_order_history=[
            {
                "po_id": "PO-2026-000001",
                "supplier_id": "SUP-00001",
                "sku_id": "SKU-000001",
                "warehouse_id": "WH-BLR-01",
                "order_date": "2026-01-10",
                "expected_date": "2026-01-20",
                "received_date": "2026-01-18",
                "quantity_ordered": "100",
                "unit_cost": "50.0",
                "po_status": "Received",
            },
            {
                "po_id": "PO-2026-000002",
                "supplier_id": "SUP-00001",
                "sku_id": "SKU-000001",
                "warehouse_id": "WH-BLR-01",
                "order_date": "2026-02-01",
                "expected_date": "2026-02-10",
                "received_date": "",
                "quantity_ordered": "50",
                "unit_cost": "50.0",
                "po_status": "Open",
            },
            {
                "po_id": "PO-2026-000003",
                "supplier_id": "SUP-00001",
                "sku_id": "SKU-000001",
                "warehouse_id": "WH-BLR-01",
                "order_date": "2026-02-15",
                "expected_date": "2026-02-25",
                "received_date": "",
                "quantity_ordered": "75",
                "unit_cost": "50.0",
                "po_status": "Cancelled",
            },
        ]
    )

    summary = import_staging_dataset(db_session, dataset, dry_run=False)
    assert summary.purchase_order_history.added == 3

    po1 = db_session.get(PurchaseOrder, "PO-2026-000001")
    assert po1 is not None
    assert po1.status == "received"
    assert po1.received_date == date(2026, 1, 18)
    assert po1.quantity == 100

    po2 = db_session.get(PurchaseOrder, "PO-2026-000002")
    assert po2 is not None
    assert po2.status == "open"
    assert po2.received_date is None

    po3 = db_session.get(PurchaseOrder, "PO-2026-000003")
    assert po3 is not None
    assert po3.status == "cancelled"


def test_purchase_order_invalid_status_rejected(db_session):
    """Unrecognized/invalid PO status raises clear validation error without silent conversion."""
    _seed_master_data(db_session)
    dataset = StagingDataset(
        purchase_order_history=[
            {
                "po_id": "PO-2026-000010",
                "supplier_id": "SUP-00001",
                "sku_id": "SKU-000001",
                "warehouse_id": "WH-BLR-01",
                "order_date": "2026-01-10",
                "expected_date": "2026-01-20",
                "quantity_ordered": "10",
                "unit_cost": "50.0",
                "po_status": "In_Progress",  # Invalid
            }
        ]
    )
    with pytest.raises(
        ClientImportValidationError, match="invalid po_status 'in_progress'"
    ):
        import_staging_dataset(db_session, dataset)


def test_purchase_order_received_missing_received_date_rejected(db_session):
    """Received PO must provide received_date; blank received_date raises validation error."""
    _seed_master_data(db_session)
    dataset = StagingDataset(
        purchase_order_history=[
            {
                "po_id": "PO-2026-000011",
                "supplier_id": "SUP-00001",
                "sku_id": "SKU-000001",
                "warehouse_id": "WH-BLR-01",
                "order_date": "2026-01-10",
                "expected_date": "2026-01-20",
                "received_date": "",  # Missing for Received status
                "quantity_ordered": "10",
                "unit_cost": "50.0",
                "po_status": "Received",
            }
        ]
    )
    with pytest.raises(
        ClientImportValidationError, match="missing received_date for Received PO"
    ):
        import_staging_dataset(db_session, dataset)


def test_purchase_order_duplicate_po_id_rejected(db_session):
    """Duplicate PO identifier in staging raises clear validation error."""
    _seed_master_data(db_session)
    dataset = StagingDataset(
        purchase_order_history=[
            {
                "po_id": "PO-2026-000012",
                "supplier_id": "SUP-00001",
                "sku_id": "SKU-000001",
                "warehouse_id": "WH-BLR-01",
                "order_date": "2026-01-10",
                "expected_date": "2026-01-20",
                "received_date": "2026-01-19",
                "quantity_ordered": "10",
                "unit_cost": "50.0",
                "po_status": "Received",
            },
            {
                "po_id": "PO-2026-000012",
                "supplier_id": "SUP-00001",
                "sku_id": "SKU-000001",
                "warehouse_id": "WH-BLR-01",
                "order_date": "2026-01-12",
                "expected_date": "2026-01-22",
                "quantity_ordered": "20",
                "unit_cost": "50.0",
                "po_status": "Open",
            },
        ]
    )
    with pytest.raises(ClientImportValidationError, match="duplicate canonical po_id"):
        import_staging_dataset(db_session, dataset)


# =========================================================================
# 3. SUPPLIER ON-TIME DELIVERY % LOGIC TESTS
# =========================================================================


def test_supplier_on_time_delivery_calculation_and_exclusions(db_session):
    """
    Verifies Section 5 and Section 9 scenario:
    Supplier SUP-00001:
      PO001 -> Received -> on time (received_date <= expected_date)
      PO002 -> Received -> late (received_date > expected_date)
      PO003 -> Cancelled (ignored)
      PO004 -> Open (ignored)
    Expected:
      Received POs = 2
      On-time POs = 1
      On-time delivery % = 50.0%
      Open and Cancelled POs do NOT affect denominator or numerator.
    """
    _seed_master_data(db_session)

    pos = [
        PurchaseOrder(
            po_id="PO-2026-000101",
            sku_id="SKU-000001",
            warehouse_id="WH-BLR-01",
            supplier_id="SUP-00001",
            quantity=10,
            unit_cost=50.0,
            expected_cost=500.0,
            status="received",
            order_date=date(2026, 1, 1),
            expected_date=date(2026, 1, 10),
            received_date=date(2026, 1, 9),  # On time (9 <= 10)
        ),
        PurchaseOrder(
            po_id="PO-2026-000102",
            sku_id="SKU-000001",
            warehouse_id="WH-BLR-01",
            supplier_id="SUP-00001",
            quantity=10,
            unit_cost=50.0,
            expected_cost=500.0,
            status="received",
            order_date=date(2026, 1, 5),
            expected_date=date(2026, 1, 15),
            received_date=date(2026, 1, 20),  # Late (20 > 15)
        ),
        PurchaseOrder(
            po_id="PO-2026-000103",
            sku_id="SKU-000001",
            warehouse_id="WH-BLR-01",
            supplier_id="SUP-00001",
            quantity=10,
            unit_cost=50.0,
            expected_cost=500.0,
            status="cancelled",
            order_date=date(2026, 1, 10),
            expected_date=date(2026, 1, 20),
            received_date=None,
        ),
        PurchaseOrder(
            po_id="PO-2026-000104",
            sku_id="SKU-000001",
            warehouse_id="WH-BLR-01",
            supplier_id="SUP-00001",
            quantity=10,
            unit_cost=50.0,
            expected_cost=500.0,
            status="open",
            order_date=date(2026, 1, 15),
            expected_date=date(2026, 1, 25),
            received_date=None,
        ),
    ]
    db_session.add_all(pos)
    db_session.commit()

    perf = get_supplier_performance(db_session, "SUP-00001")
    assert perf is not None
    assert perf.supplier_id == "SUP-00001"
    assert perf.received_po_count == 2
    assert perf.on_time_po_count == 1
    assert perf.late_po_count == 1
    assert perf.open_po_count == 1
    assert perf.cancelled_po_count == 1
    assert perf.total_po_count == 4
    assert perf.on_time_delivery_percent == 50.0


def test_supplier_with_no_received_pos_avoids_zero_division(db_session):
    """Supplier with zero Received POs safely returns 0.0% without ZeroDivisionError."""
    _seed_master_data(db_session)

    # Only an open PO for SUP-00002
    db_session.add(
        PurchaseOrder(
            po_id="PO-2026-000201",
            sku_id="SKU-000002",
            warehouse_id="WH-BOM-01",
            supplier_id="SUP-00002",
            quantity=5,
            unit_cost=80.0,
            expected_cost=400.0,
            status="open",
            order_date=date(2026, 2, 1),
            expected_date=date(2026, 2, 10),
            received_date=None,
        )
    )
    db_session.commit()

    perf = get_supplier_performance(db_session, "SUP-00002")
    assert perf is not None
    assert perf.received_po_count == 0
    assert perf.on_time_po_count == 0
    assert perf.on_time_delivery_percent is None
    assert perf.open_po_count == 1


# =========================================================================
# 4. API ENDPOINT TESTS
# =========================================================================


def test_api_supplier_performance_endpoints(client):
    """Test GET /api/v1/inventory/suppliers/performance endpoints."""
    from tests.conftest import TestingSessionLocal

    db = TestingSessionLocal()
    try:
        _seed_master_data(db)
        db.add(
            PurchaseOrder(
                po_id="PO-2026-000301",
                sku_id="SKU-000001",
                warehouse_id="WH-BLR-01",
                supplier_id="SUP-00001",
                quantity=10,
                unit_cost=50.0,
                expected_cost=500.0,
                status="received",
                order_date=date(2026, 1, 1),
                expected_date=date(2026, 1, 10),
                received_date=date(2026, 1, 10),  # On time (exact boundary)
            )
        )
        db.commit()
    finally:
        db.close()

    # 1. Get all suppliers performance
    resp_all = client.get("/api/v1/inventory/suppliers/performance")
    assert resp_all.status_code == 200
    data_all = resp_all.json()
    assert isinstance(data_all, list)
    assert any(item["supplier_id"] == "SUP-00001" for item in data_all)

    sup1_item = next(item for item in data_all if item["supplier_id"] == "SUP-00001")
    assert sup1_item["received_po_count"] == 1
    assert sup1_item["on_time_po_count"] == 1
    assert sup1_item["on_time_delivery_percent"] == 100.0

    # 2. Filter by query param ?supplier_id=SUP-00001
    resp_filter = client.get(
        "/api/v1/inventory/suppliers/performance?supplier_id=SUP-00001"
    )
    assert resp_filter.status_code == 200
    assert len(resp_filter.json()) == 1
    assert resp_filter.json()[0]["supplier_id"] == "SUP-00001"

    # 3. Path parameter /api/v1/inventory/suppliers/{supplier_id}/performance
    resp_single = client.get("/api/v1/inventory/suppliers/SUP-00001/performance")
    assert resp_single.status_code == 200
    data_single = resp_single.json()
    assert data_single["supplier_id"] == "SUP-00001"
    assert data_single["received_po_count"] == 1
    assert data_single["on_time_delivery_percent"] == 100.0

    # 4. Unknown supplier returns 404
    resp_404 = client.get("/api/v1/inventory/suppliers/SUP-NONEXIST/performance")
    assert resp_404.status_code == 404
    assert "not found" in resp_404.json().get("detail", "").lower()

    # 5. Route collision protection: /suppliers/performance has two path segments
    # and must NOT be captured by /{sku_id}/{warehouse_id}.
    # If captured by /{sku_id}/{warehouse_id}, it would return 404 {"detail": "Inventory not found"}.
    assert resp_all.status_code == 200
    assert isinstance(data_all, list)
    assert resp_single.status_code == 200
    assert data_single.get("supplier_id") == "SUP-00001"


# =========================================================================
# 5. END-TO-END REORDER RECOMMENDATION WORKFLOW (SECTION 8 - 11 QUESTIONS)
# =========================================================================


def test_end_to_end_client_data_readiness_and_reorder_summary(tmp_path, db_session):
    """
    Demonstrates the complete end-to-end Issue #325 pipeline:
    Client snapshot + PO history -> Import -> Canonical mapping -> Existing Reorder logic -> Summary.
    Directly answers all 11 questions from Issue #325 Section 8:
    1. How many inventory records were imported?
    2. How many PO records were imported?
    3. How many records were rejected?
    4. Which SKUs are below reorder point?
    5. What quantity is recommended?
    6. Which supplier is recommended?
    7. Which reorder-point/safety-stock values came from the client?
    8. Which values were calculated as fallback?
    9. What is the supplier on-time delivery percentage?
    10. Were Open POs ignored for on-time delivery?
    11. Were Cancelled POs ignored for on-time delivery?
    """
    _seed_master_data(db_session)

    # 1. Prepare synthetic client-shaped files in staging directory
    snapshot_csv = tmp_path / "inventory_snapshot.csv"
    with snapshot_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "snapshot_date",
                "sku_id",
                "warehouse_id",
                "quantity_on_hand",
                "quantity_reserved",
                "reorder_point",
                "safety_stock",
            ]
        )
        # Item 1: SKU-000001 below imported ROP (QOH=5 < ROP=25) -> Needs reorder
        w.writerow(["2026-11-10", "SKU-000001", "WH-BLR-01", "5", "0", "25", "10"])
        # Item 2: SKU-000002 above imported ROP (QOH=100 >= ROP=50) -> No reorder
        w.writerow(["2026-11-10", "SKU-000002", "WH-BOM-01", "100", "0", "50", "15"])
        # Item 3: Missing ROP & safety stock -> Trigger calculated fallback
        w.writerow(["2026-11-10", "SKU-000001", "WH-BOM-01", "2", "0", "", ""])

    po_csv = tmp_path / "purchase_order_history.csv"
    with po_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "po_id",
                "supplier_id",
                "sku_id",
                "warehouse_id",
                "order_date",
                "expected_date",
                "received_date",
                "quantity_ordered",
                "unit_cost",
                "po_status",
            ]
        )
        # Received on-time (2026-01-08 <= 2026-01-10)
        w.writerow(
            [
                "PO-2026-000001",
                "SUP-00001",
                "SKU-000001",
                "WH-BLR-01",
                "2026-01-01",
                "2026-01-10",
                "2026-01-08",
                "50",
                "50.0",
                "Received",
            ]
        )
        # Received late (2026-01-25 > 2026-01-20)
        w.writerow(
            [
                "PO-2026-000002",
                "SUP-00001",
                "SKU-000001",
                "WH-BLR-01",
                "2026-01-05",
                "2026-01-20",
                "2026-01-25",
                "50",
                "50.0",
                "Received",
            ]
        )
        # Open (ignored for delivery %)
        w.writerow(
            [
                "PO-2026-000003",
                "SUP-00001",
                "SKU-000001",
                "WH-BLR-01",
                "2026-02-01",
                "2026-02-15",
                "",
                "30",
                "50.0",
                "Open",
            ]
        )
        # Cancelled (ignored for delivery %)
        w.writerow(
            [
                "PO-2026-000004",
                "SUP-00001",
                "SKU-000001",
                "WH-BLR-01",
                "2026-02-05",
                "2026-02-20",
                "",
                "40",
                "50.0",
                "Cancelled",
            ]
        )

    # 2. Execute import via run_client_data_import
    summary = run_client_data_import(db=db_session, staging_dir=tmp_path, dry_run=False)

    # Question 1: How many inventory records were imported?
    assert summary.inventory_snapshots.added == 3
    # Question 2: How many PO records were imported?
    assert summary.purchase_order_history.added == 4
    # Question 3: How many records were rejected?
    # Valid batch -> 0 rejected

    # Question 4: Which SKUs are below reorder point?
    below_rop_items = [
        rec for rec in summary.reorder_recommendations if rec.needs_reorder
    ]
    assert any(
        r.sku_id == "SKU-000001" and r.warehouse_id == "WH-BLR-01"
        for r in below_rop_items
    )

    # Item at WH-BLR-01: QOH=5, ROP=25 -> shortage=20
    blr_item = next(r for r in below_rop_items if r.warehouse_id == "WH-BLR-01")
    # Question 5: What quantity is recommended?
    assert blr_item.suggested_quantity == 20
    # Question 6: Which supplier is recommended?
    assert blr_item.supplier_id == "SUP-00001"
    assert blr_item.expected_cost == 20 * 50.0

    # Question 7: Which reorder-point/safety-stock values came from the client?
    imported_records = [
        r for r in summary.snapshot_records if r.reorder_point_source == "imported"
    ]
    assert len(imported_records) == 2
    assert {r.warehouse_id for r in imported_records} == {"WH-BLR-01", "WH-BOM-01"}

    # Question 8: Which values were calculated as fallback?
    calc_records = [
        r for r in summary.snapshot_records if r.reorder_point_source == "calculated"
    ]
    assert len(calc_records) == 1
    assert calc_records[0].warehouse_id == "WH-BOM-01"
    assert calc_records[0].fallback_reason == "missing from client snapshot"

    # Question 9: What is the supplier on-time delivery percentage?
    # Question 10: Were Open POs ignored for on-time delivery?
    # Question 11: Were Cancelled POs ignored for on-time delivery?
    sup1_perf = next(
        sp for sp in summary.supplier_performance if sp.supplier_id == "SUP-00001"
    )
    assert sup1_perf.received_po_count == 2
    assert sup1_perf.on_time_po_count == 1
    assert sup1_perf.open_po_count == 1
    assert sup1_perf.cancelled_po_count == 1
    assert sup1_perf.on_time_delivery_percent == 50.0  # (1 on-time / 2 received) * 100

    # Formatted summary string check
    formatted = summary.format_summary()
    assert "Inventory snapshots:" in formatted
    assert "Purchase orders:" in formatted
    assert "Supplier on-time delivery performance:" in formatted
    assert "Reorder recommendations:" in formatted
    assert "50.0%" in formatted


# =========================================================================
# 6. REGRESSION TESTS FOR REVIEW ITEMS (MUST-FIX 1-4)
# =========================================================================


def _po_row(po_id: str, supplier_id: str, status: str, **dates: str) -> dict[str, str]:
    row = {
        "po_id": po_id,
        "supplier_id": supplier_id,
        "sku_id": "SKU-000001",
        "warehouse_id": "WH-BLR-01",
        "order_date": "2026-03-01",
        "expected_date": "2026-03-10",
        "received_date": "",
        "quantity_ordered": "10",
        "unit_cost": "50.0",
        "po_status": status,
    }
    row.update(dates)
    return row


def test_summary_prints_supplier_with_only_open_pos(db_session):
    """A supplier with no dated Received POs has no on-time %, and the summary still prints."""
    _seed_master_data(db_session)
    dataset = StagingDataset(
        purchase_order_history=[_po_row("PO-2026-000101", "SUP-00002", "Open")]
    )
    summary = import_staging_dataset(db_session, dataset, dry_run=False)
    perf = {p.supplier_id: p for p in summary.supplier_performance}
    assert perf["SUP-00002"].on_time_delivery_percent is None
    assert "SUP-00002 (Beta Logistics Supply): n/a" in summary.format_summary()


def test_summary_counts_default_safety_stock_fallbacks(db_session):
    """A missing safety_stock is counted as a default fallback in the summary."""
    _seed_master_data(db_session)
    dataset = StagingDataset(
        inventory_snapshots=[
            {
                "sku_id": "SKU-000002",
                "warehouse_id": "WH-BOM-01",
                "quantity_on_hand": "45",
                "reorder_point": "30",
                "safety_stock": "",
            }
        ]
    )
    summary = import_staging_dataset(db_session, dataset, dry_run=False)
    assert "Safety stocks: imported=0, default_fallback=1" in summary.format_summary()


@pytest.mark.parametrize(
    "dates, field",
    [
        ({"expected_date": "2026-02-20"}, "expected_date"),
        ({"received_date": "2026-02-25"}, "received_date"),
    ],
)
def test_purchase_order_dates_before_order_date_rejected(db_session, dates, field):
    """A PO cannot be expected or received before it was ordered."""
    _seed_master_data(db_session)
    row = _po_row(
        "PO-2026-000102",
        "SUP-00001",
        "Received",
        **{"received_date": "2026-03-05", **dates},
    )
    dataset = StagingDataset(purchase_order_history=[row])
    with pytest.raises(
        ClientImportValidationError, match=f"{field} .* is before order_date"
    ):
        import_staging_dataset(db_session, dataset, dry_run=True)


def test_csv_row_with_extra_cells_is_rejected(tmp_path):
    from app.services.client_import_service import (
        ClientImportValidationError,
        _read_csv_records,
    )

    path = tmp_path / "inventory_snapshots.csv"
    path.write_text(
        "sku_id,warehouse_id,quantity_on_hand\nSKU-000001,WH-BLR-01,5,999\n",
        encoding="utf-8",
    )
    with pytest.raises(ClientImportValidationError, match="line 2"):
        _read_csv_records(path, "inventory_snapshots")
