import random

from app.database import Base, SessionLocal, engine
from app.models.supplier import Supplier


# ============================================================
# SETTINGS
# ============================================================

TOTAL_ITEMS = 50

SUPPLIER_NAMES = [
    "ABC Supplies",
    "Global Traders",
    "Prime Distributors",
    "Fast Supply Co",
    "Office Supply Partners",
    "Reliable Wholesale",
    "National Suppliers",
    "Metro Distributors",
    "Universal Traders",
    "Best Source Ltd",
]


def seed_suppliers():

    # Create tables if they do not exist
    Base.metadata.create_all(
        bind=engine
    )

    db = SessionLocal()

    try:

        # Make results repeatable
        random.seed(42)

        suppliers = []

        # ====================================================
        # Generate 2 suppliers for every SKU
        # SKU001 -> 2 suppliers
        # SKU002 -> 2 suppliers
        # ...
        # SKU050 -> 2 suppliers
        # ====================================================

        supplier_number = 1

        for item_number in range(
            1,
            TOTAL_ITEMS + 1
        ):

            sku_id = f"SKU{item_number:03d}"

            # --------------------------------------------
            # Supplier 1
            # --------------------------------------------

            supplier1 = Supplier(
                supplier_id=f"SUP{supplier_number:03d}",
                supplier_name=SUPPLIER_NAMES[
                    (supplier_number - 1)
                    % len(SUPPLIER_NAMES)
                ],
                sku_id=sku_id,
                unit_cost=round(
                    random.uniform(20.00, 100.00),
                    2
                ),
                lead_time_days=random.randint(
                    3,
                    10
                ),
            )

            suppliers.append(supplier1)

            supplier_number += 1

            # --------------------------------------------
            # Supplier 2
            # --------------------------------------------

            supplier2 = Supplier(
                supplier_id=f"SUP{supplier_number:03d}",
                supplier_name=SUPPLIER_NAMES[
                    (supplier_number - 1)
                    % len(SUPPLIER_NAMES)
                ],
                sku_id=sku_id,
                unit_cost=round(
                    random.uniform(20.00, 100.00),
                    2
                ),
                lead_time_days=random.randint(
                    3,
                    10
                ),
            )

            suppliers.append(supplier2)

            supplier_number += 1

        # ====================================================
        # Insert only suppliers that do not already exist
        # ====================================================

        print(
            "\nInserting supplier records..."
        )

        inserted = 0
        skipped = 0

        for supplier in suppliers:

            existing = (
                db.query(Supplier)
                .filter(
                    Supplier.supplier_id
                    == supplier.supplier_id
                )
                .first()
            )

            if existing:

                skipped += 1

                print(
                    f"{supplier.supplier_id} already exists"
                )

                continue

            db.add(supplier)
            inserted += 1

        db.commit()

        # ====================================================
        # Verify
        # ====================================================

        total_records = (
            db.query(Supplier).count()
        )

        unique_skus = (
            db.query(Supplier.sku_id)
            .distinct()
            .count()
        )

        # ====================================================
        # Display result
        # ====================================================

        print(
            "\n========================================"
        )
        print(
            "        SUPPLIER SEED COMPLETE"
        )
        print(
            "========================================"
        )

        print(
            f"Expected suppliers : "
            f"{TOTAL_ITEMS * 2}"
        )

        print(
            f"Inserted suppliers : "
            f"{inserted}"
        )

        print(
            f"Skipped suppliers  : "
            f"{skipped}"
        )

        print(
            f"Total in database  : "
            f"{total_records}"
        )

        print(
            f"Unique SKUs        : "
            f"{unique_skus}"
        )

        print(
            "========================================"
        )

        # ====================================================
        # Display sample
        # ====================================================

        print(
            "\nSample supplier data:"
        )

        sample = (
            db.query(Supplier)
            .order_by(
                Supplier.sku_id,
                Supplier.supplier_id
            )
            .limit(10)
            .all()
        )

        for row in sample:

            print(
                f"{row.supplier_id} | "
                f"{row.supplier_name} | "
                f"{row.sku_id} | "
                f"{row.unit_cost} | "
                f"{row.lead_time_days} days"
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
    seed_suppliers()