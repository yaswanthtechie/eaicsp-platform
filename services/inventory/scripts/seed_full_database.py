#!/usr/bin/env python3
"""
Seed Full Database Script (Round 15)
Populates ALL tables in PostgreSQL:
- warehouses
- products
- suppliers
- inventory (current stock)
- inventory_cost_layers (FIFO cost layers)
- sales_history
- purchase_orders
- outbox
- supplier_compliance_states
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys

# Setup paths
SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_DIR = SCRIPT_DIR.parent
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from app.database import SessionLocal
from app.models.inventory import Inventory
from app.models.inventory_cost_layer import InventoryCostLayer
from app.models.outbox import Outbox
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.sales_history import SalesHistory
from app.models.supplier import Supplier
from app.models.warehouse import Warehouse
from app.models.compliance_event import SupplierComplianceState
from scripts.load_seed import run_loader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_full_database")

def seed():
    # 1. Run canonical seed loader from data-platform/out
    logger.info("Step 1: Running canonical master data loader (warehouses, products, suppliers, sales, inventory)...")
    repo_root = SERVICE_DIR.parent.parent
    seed_dir = repo_root / "data-platform" / "out"
    
    loader_result = run_loader(seed_dir_path=str(seed_dir), wipe=True)
    logger.info("Canonical master data loaded: %s", loader_result)

    db = SessionLocal()
    try:
        # 2. Seed Sample Purchase Orders
        logger.info("Step 2: Seeding sample Purchase Orders...")
        existing_pos = {po.po_id for po in db.query(PurchaseOrder.po_id).all()}
        
        sample_pos = [
            PurchaseOrder(
                po_id="PO-2026-000123",
                sku_id="SKU-000001",
                warehouse_id="WH-BLR-01",
                supplier_id="SUP-00019",
                quantity=100,
                unit_cost=75.00,
                expected_cost=7500.00,
                status="approved",
                approval_status="approved",
                hold_reason=None,
                hold_source=None,
                created_at=datetime.now(UTC) - timedelta(days=2),
            ),
            PurchaseOrder(
                po_id="PO-2026-000124",
                sku_id="SKU-000004",
                warehouse_id="WH-DEL-01",
                supplier_id="SUP-00007",  # Sanctioned entity
                quantity=50,
                unit_cost=2900.00,
                expected_cost=145000.00,
                status="compliance_hold",
                approval_status="pending_vp_approval",
                hold_reason="Matched OFAC-SDN Sanctions Watchlist",
                hold_source="compliance_service",
                created_at=datetime.now(UTC) - timedelta(days=1),
            ),
            PurchaseOrder(
                po_id="PO-2026-000125",
                sku_id="SKU-000002",
                warehouse_id="WH-BOM-01",
                supplier_id="SUP-00021",
                quantity=80,
                unit_cost=280.00,
                expected_cost=22400.00,
                status="acknowledged",
                approval_status="approved",
                hold_reason=None,
                hold_source=None,
                created_at=datetime.now(UTC) - timedelta(days=3),
            ),
            PurchaseOrder(
                po_id="PO-2026-000126",
                sku_id="SKU-000003",
                warehouse_id="WH-BLR-01",
                supplier_id="SUP-00022",
                quantity=200,
                unit_cost=210.00,
                expected_cost=42000.00,
                status="draft",
                approval_status="pending_vp_approval",
                hold_reason=None,
                hold_source=None,
                created_at=datetime.now(UTC),
            ),
        ]
        
        for po in sample_pos:
            if po.po_id not in existing_pos:
                db.add(po)

        # 3. Seed Sample Outbox Events
        logger.info("Step 3: Seeding sample Outbox events...")
        existing_outbox = {o.aggregate_id for o in db.query(Outbox.aggregate_id).all()}
        
        po_approved_payload = {
            "event_id": "c5a08902-60d7-4ee4-9efc-70335804360b",
            "event_type": "inventory.po.approved",
            "event_version": 1,
            "occurred_at": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
            "producer": "inventory-service",
            "trace_id": "trace-seed-001",
            "payload": {
                "po_id": "PO-2026-000123",
                "po_number": "PO-2026-000123",
                "supplier_id": "SUP-00019",
                "warehouse_id": "WH-BLR-01",
                "approval_status": "approved",
                "approved_by": "e6a2b8e4-18c2-4d2b-8a71-419b48b11111",
                "approved_at": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
                "total_amount": 7500.0,
                "currency": "INR",
                "expected_delivery_date": (datetime.now(UTC) + timedelta(days=10)).strftime("%Y-%m-%d"),
                "lines": [
                    {
                        "line_number": 1,
                        "sku_id": "SKU-000001",
                        "quantity": 100,
                        "unit_cost": 75.0,
                        "expected_cost": 7500.0,
                    }
                ]
            }
        }
        
        if "PO-2026-000123" not in existing_outbox:
            db.add(Outbox(
                event_type="inventory.po.approved",
                aggregate_type="PurchaseOrder",
                aggregate_id="PO-2026-000123",
                payload=json.dumps(po_approved_payload),
                status="published",
                published_at=datetime.now(UTC),
            ))

        # 4. Seed Supplier Compliance States
        logger.info("Step 4: Seeding Supplier Compliance States...")
        existing_comp = {s.supplier_id for s in db.query(SupplierComplianceState.supplier_id).all()}
        
        comp_states = [
            SupplierComplianceState(
                supplier_id="SUP-00007",
                last_status="blocked",
                last_occurred_at=datetime.now(UTC) - timedelta(days=10),
                last_reason="OFAC-SDN Sanctioned",
            ),
            SupplierComplianceState(
                supplier_id="SUP-00023",
                last_status="blocked",
                last_occurred_at=datetime.now(UTC) - timedelta(days=10),
                last_reason="EU-CONSOLIDATED Sanctioned",
            ),
            SupplierComplianceState(
                supplier_id="SUP-00045",
                last_status="blocked",
                last_occurred_at=datetime.now(UTC) - timedelta(days=10),
                last_reason="UN-SC Sanctioned",
            ),
            SupplierComplianceState(
                supplier_id="SUP-00019",
                last_status="cleared",
                last_occurred_at=datetime.now(UTC) - timedelta(days=10),
                last_reason="Screening passed",
            ),
            SupplierComplianceState(
                supplier_id="SUP-00021",
                last_status="cleared",
                last_occurred_at=datetime.now(UTC) - timedelta(days=10),
                last_reason="Screening passed",
            ),
        ]
        
        for cs in comp_states:
            if cs.supplier_id not in existing_comp:
                db.add(cs)

        db.commit()
        logger.info("All tables successfully committed!")

        # 5. Print Verification Counts
        print("\n" + "=" * 50)
        print("     DATABASE POPULATION VERIFICATION SUMMARY")
        print("=" * 50)
        counts = {
            "warehouses": db.query(Warehouse).count(),
            "products": db.query(Product).count(),
            "suppliers": db.query(Supplier).count(),
            "inventory": db.query(Inventory).count(),
            "inventory_cost_layers": db.query(InventoryCostLayer).count(),
            "sales_history": db.query(SalesHistory).count(),
            "purchase_orders": db.query(PurchaseOrder).count(),
            "outbox": db.query(Outbox).count(),
            "supplier_compliance_states": db.query(SupplierComplianceState).count(),
        }
        for table, count in counts.items():
            print(f"  ✓  {table:<28} : {count:>6} rows")
        print("=" * 50 + "\n")

    except Exception as exc:
        db.rollback()
        logger.error("Failed to seed database: %s", exc)
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed()

