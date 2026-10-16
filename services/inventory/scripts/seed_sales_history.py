from datetime import date, timedelta
import random
import sys
from pathlib import Path

# Setup path so app can be imported when running script directly
SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_DIR = SCRIPT_DIR.parent
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from app.database import Base, SessionLocal, engine
from app.models.sales_history import SalesHistory
from app.models.inventory import Inventory
from app.services.demand_service import calculate_rolling_average_demand


# ============================================================
# SETTINGS
# ============================================================

TOTAL_ITEMS = 50
TOTAL_DAYS = 30

WAREHOUSES = [
    "WH-BLR-01",
    "WH-CCU-01",
    "WH-DEL-01",
    "WH-HYD-01",
    "WH-MAA-01",
    "WH-BOM-01",
]


def seed_sales_history():

    # Create tables if they do not exist
    Base.metadata.create_all(
        bind=engine
    )

    db = SessionLocal()

    try:

        # ====================================================
        # 1. Clear old sales-history data
        # ====================================================

        print(
            "Deleting old sales-history records..."
        )

        db.query(SalesHistory).delete()

        db.commit()

        # ====================================================
        # 2. Generate 50 SKUs
        # ====================================================

        today = date.today()

        sales_records = []

        # Make results repeatable
        random.seed(42)

        for item_number in range(
            1,
            TOTAL_ITEMS + 1
        ):

            # Canonical SKU ID format: SKU-000001 .. SKU-000050
            sku_id = f"SKU-{item_number:06d}"

            # Canonical warehouse pattern matching warehouses seed
            warehouse_id = WAREHOUSES[
                (item_number - 1)
                % len(WAREHOUSES)
            ]


            # Each SKU gets its own demand level
            base_demand = random.randint(
                10,
                60
            )

            # =================================================
            # 30 DAYS OF SALES
            # =================================================

            for days_ago in range(
                TOTAL_DAYS - 1,
                -1,
                -1
            ):

                sale_date = (
                    today
                    - timedelta(days=days_ago)
                )

                # Random daily variation
                variation = random.uniform(
                    0.80,
                    1.20
                )

                quantity_sold = int(
                    base_demand * variation
                )

                # Make sure sales are never too low
                quantity_sold = max(
                    5,
                    quantity_sold
                )

                sales_record = SalesHistory(
                    sku_id=sku_id,
                    warehouse_id=warehouse_id,
                    sale_date=sale_date,
                    quantity_sold=quantity_sold,
                )

                sales_records.append(
                    sales_record
                )

            if item_number % 10 == 0:

                print(
                    f"Generated "
                    f"{item_number}/{TOTAL_ITEMS} "
                    "SKUs"
                )

        # Also generate sales history for any existing Inventory items
        existing_inventories = db.query(Inventory).all()
        covered_pairs = {
            (
                f"SKU-{n:06d}",
                WAREHOUSES[(n - 1) % len(WAREHOUSES)],
            )
            for n in range(1, TOTAL_ITEMS + 1)
        }

        for inv in existing_inventories:
            pair = (inv.sku_id, inv.warehouse_id)
            if pair in covered_pairs:
                continue
            covered_pairs.add(pair)
            base_demand = random.randint(15, 45)
            for days_ago in range(TOTAL_DAYS - 1, -1, -1):
                sale_date = today - timedelta(days=days_ago)
                variation = random.uniform(0.80, 1.20)
                quantity_sold = max(5, int(base_demand * variation))
                sales_records.append(
                    SalesHistory(
                        sku_id=inv.sku_id,
                        warehouse_id=inv.warehouse_id,
                        sale_date=sale_date,
                        quantity_sold=quantity_sold,
                    )
                )

        # ====================================================
        # 3. Insert all records
        # ====================================================

        print(
            "\nInserting sales-history records..."
        )

        db.bulk_save_objects(
            sales_records
        )

        db.commit()

        # Update rolling avg_daily_demand on all Inventory items
        for inv in db.query(Inventory).all():
            inv.avg_daily_demand = calculate_rolling_average_demand(
                db, inv.sku_id, inv.warehouse_id
            )
        db.commit()

        # ====================================================
        # 4. Verify total records
        # ====================================================

        total_records = (
            db.query(
                SalesHistory
            ).count()
        )

        unique_skus = (
            db.query(
                SalesHistory.sku_id
            )
            .distinct()
            .count()
        )

        unique_warehouses = (
            db.query(
                SalesHistory.warehouse_id
            )
            .distinct()
            .count()
        )

        # ====================================================
        # 5. Display result
        # ====================================================

        print(
            "\n========================================"
        )
        print(
            "     SALES HISTORY SEED COMPLETE"
        )
        print(
            "========================================"
        )

        print(
            f"Expected records : "
            f"{TOTAL_ITEMS * TOTAL_DAYS}"
        )

        print(
            f"Actual records   : "
            f"{total_records}"
        )

        print(
            f"Unique SKUs      : "
            f"{unique_skus}"
        )

        print(
            f"Warehouses       : "
            f"{unique_warehouses}"
        )

        print(
            f"Days per SKU     : "
            f"{TOTAL_DAYS}"
        )

        print(
            "========================================"
        )

        # ====================================================
        # 6. Display sample
        # ====================================================

        print(
            "\nSample data:"
        )

        sample = (
            db.query(SalesHistory)
            .order_by(
                SalesHistory.sku_id,
                SalesHistory.sale_date
            )
            .limit(15)
            .all()
        )

        for row in sample:

            print(
                f"{row.sku_id} | "
                f"{row.warehouse_id} | "
                f"{row.sale_date} | "
                f"{row.quantity_sold}"
            )

    except Exception as e:

        db.rollback()

        print(
            f"\nERROR: {e}"
        )

        raise

    finally:

        db.close()


if __name__ == "__main__":
    seed_sales_history()