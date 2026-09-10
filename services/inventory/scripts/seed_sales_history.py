from datetime import date, timedelta
import random
random.seed(42)

from app.database import Base, SessionLocal, engine
from app.models.sales_history import SalesHistory


# ============================================================
# SETTINGS
# ============================================================

TOTAL_ITEMS = 50
TOTAL_DAYS = 30

WAREHOUSES = [
    "WH001",
    "WH002",
    "WH003",
    "WH004",
    "WH005",
]


def seed_sales_history():

    # Create tables if they do not exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:

        # ====================================================
        # 1. Generate 50 SKUs
        # ====================================================

        today = date.today()

        sales_records = []

        for item_number in range(
            1,
            TOTAL_ITEMS + 1
        ):

            sku_id = f"SKU{item_number:04d}"

            # IMPORTANT:
            # Same warehouse must later be used
            # in your inventory CSV.
            warehouse_id = WAREHOUSES[
                (item_number - 1)
                % len(WAREHOUSES)
            ]

            # Each SKU gets its own realistic
            # average demand.
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

                # Make sure quantity is never 0 or 1
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

        # ====================================================
        # 2. Insert all 1,500 records
        # ====================================================

        print(
            "\nInserting sales-history records..."
        )

        db.bulk_save_objects(
            sales_records
        )

        db.commit()

        # ====================================================
        # 3. Verify
        # ====================================================

        total_records = (
            db.query(SalesHistory).count()
        )

        unique_skus = (
            db.query(
                SalesHistory.sku_id
            )
            .distinct()
            .count()
        )

        print("\n========================================")
        print("     SALES HISTORY SEED COMPLETE")
        print("========================================")

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
            f"Days per SKU     : "
            f"{TOTAL_DAYS}"
        )

        print("========================================")

        # ====================================================
        # 4. Display sample
        # ====================================================

        print("\nSample data:")

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