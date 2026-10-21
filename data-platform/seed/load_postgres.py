
"""Load the Round 15 canonical CSV dataset into PostgreSQL.

Database connection priority:
1. DATABASE_URL environment variable, when provided.
2. Database settings from the repository root .env file.

The loader replaces canonical seed records and canonical SKU-% sales history.
Legacy sales rows using IDs such as SKU001 are preserved.
"""

import argparse
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import URL


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data-platform" / "out"
ENV_FILE = ROOT / ".env"
SCHEMA = "inventory"


def get_database_url():
    """Return a database URL from the environment or the root .env file."""
    database_url = os.environ.get("DATABASE_URL")

    if database_url:
        return database_url

    env_values = {}

    if ENV_FILE.is_file():
        for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            env_values[key.strip()] = value.strip()

    required = ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")
    missing = [
        key for key in required
        if not env_values.get(key)
    ]

    if missing:
        raise RuntimeError(
            "Database configuration is missing. Set DATABASE_URL or "
            f"configure these keys in {ENV_FILE}: {', '.join(missing)}"
        )

    return URL.create(
        drivername="postgresql+psycopg2",
        username=env_values["POSTGRES_USER"],
        password=env_values["POSTGRES_PASSWORD"],
        host=env_values.get("POSTGRES_HOST", "127.0.0.1"),
        port=int(env_values.get("POSTGRES_PORT", "5432")),
        database=env_values["POSTGRES_DB"],
    )


def copy_csv(cursor, table, columns, filename):
    """Copy a generated CSV file into a PostgreSQL table."""
    path = DATA_DIR / filename

    if not path.is_file():
        raise FileNotFoundError(
            f"Required seed file not found: {path}. "
            "Generate the dataset before loading it."
        )

    column_sql = ", ".join(columns)
    statement = (
        f"COPY {SCHEMA}.{table} ({column_sql}) "
        "FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
    )

    with path.open("r", encoding="utf-8", newline="") as source:
        cursor.copy_expert(statement, source)


def count_rows(cursor, table):
    """Return the row count for a known seed table."""
    cursor.execute(f"SELECT COUNT(*) FROM {SCHEMA}.{table}")
    return cursor.fetchone()[0]


def load(refresh_inventory=False):
    """Load canonical data in one transaction."""
    database_url = get_database_url()
    engine = create_engine(database_url, pool_pre_ping=True)
    connection = engine.raw_connection()

    try:
        cursor = connection.cursor()

        # Replace canonical data only. Delete child records before parent
        # records to respect foreign-key constraints.
        cursor.execute(f"DELETE FROM {SCHEMA}.canonical_opening_stock")
        cursor.execute(f"DELETE FROM {SCHEMA}.canonical_skus")
        cursor.execute(f"DELETE FROM {SCHEMA}.canonical_suppliers")
        cursor.execute(f"DELETE FROM {SCHEMA}.canonical_warehouses")

        # Preserve legacy SKU001-style sales rows.
        cursor.execute(
            f"DELETE FROM {SCHEMA}.sales_history WHERE sku_id LIKE 'SKU-%'"
        )

        copy_csv(
            cursor,
            "canonical_warehouses",
            [
                "warehouse_id", "name", "city", "state",
                "lat", "lng", "capacity_units", "demand_weight",
            ],
            "warehouses.csv",
        )

        copy_csv(
            cursor,
            "canonical_suppliers",
            [
                "supplier_id", "name", "country", "city", "state",
                "lat", "lng", "sanctions_flag", "sanctions_list",
                "lead_time_days", "payment_terms_days", "reliability_score",
            ],
            "suppliers.csv",
        )

        copy_csv(
            cursor,
            "canonical_skus",
            [
                "sku_id", "name", "category", "pack_size",
                "unit_price", "unit_cost", "abc_class", "supplier_id",
            ],
            "skus.csv",
        )

        copy_csv(
            cursor,
            "canonical_opening_stock",
            [
                "snapshot_date", "sku_id",
                "warehouse_id", "quantity_on_hand",
            ],
            "opening_stock.csv",
        )

        # CSV column order: sale_date, sku_id, warehouse_id,
        # quantity_sold, unit_price.
        copy_csv(
            cursor,
            "sales_history",
            [
                "sale_date", "sku_id", "warehouse_id",
                "quantity_sold", "unit_price",
            ],
            "sales_daily.csv",
        )

        conflict_sql = (
            """
            ON CONFLICT (sku_id, warehouse_id) DO UPDATE SET
                product_name = EXCLUDED.product_name,
                category = EXCLUDED.category,
                quantity_on_hand = EXCLUDED.quantity_on_hand,
                avg_daily_demand = EXCLUDED.avg_daily_demand,
                lead_time_days = EXCLUDED.lead_time_days,
                safety_stock = EXCLUDED.safety_stock,
                version = inventory.version + 1
            """
            if refresh_inventory
            else "ON CONFLICT (sku_id, warehouse_id) DO NOTHING"
        )

        # Populate operational inventory using canonical opening stock
        # and the average quantity sold per day.
        cursor.execute(
            f"""
            INSERT INTO {SCHEMA}.inventory (
                sku_id, warehouse_id, product_name, category,
                quantity_on_hand, avg_daily_demand, lead_time_days,
                safety_stock, warehouse_type, version
            )
            SELECT
                s.sku_id,
                o.warehouse_id,
                s.name,
                s.category,
                o.quantity_on_hand,
                COALESCE(d.avg_daily_demand, 0.0),
                COALESCE(sup.lead_time_days, 14),
                GREATEST(
                    0,
                    CEIL(
                        COALESCE(d.avg_daily_demand, 0.0)
                        * SQRT(
                            COALESCE(sup.lead_time_days, 14)::double precision
                        )
                        * 1.65
                    )::integer
                ),
                'local',
                1
            FROM {SCHEMA}.canonical_opening_stock AS o
            JOIN {SCHEMA}.canonical_skus AS s
              ON s.sku_id = o.sku_id
            JOIN {SCHEMA}.canonical_suppliers AS sup
              ON sup.supplier_id = s.supplier_id
            LEFT JOIN (
                SELECT
                    sku_id,
                    warehouse_id,
                    AVG(quantity_sold)::double precision AS avg_daily_demand
                FROM {SCHEMA}.sales_history
                WHERE sku_id LIKE 'SKU-%'
                GROUP BY sku_id, warehouse_id
            ) AS d
              ON d.sku_id = o.sku_id
             AND d.warehouse_id = o.warehouse_id
            {conflict_sql}
            """
        )

        # Verify every canonical SKU references an existing supplier.
        cursor.execute(
            f"""
            SELECT COUNT(*)
            FROM {SCHEMA}.canonical_skus AS s
            LEFT JOIN {SCHEMA}.canonical_suppliers AS sup
              ON sup.supplier_id = s.supplier_id
            WHERE sup.supplier_id IS NULL
            """
        )
        orphan_skus = cursor.fetchone()[0]

        if orphan_skus:
            raise RuntimeError(
                f"Found {orphan_skus} canonical SKUs without a supplier."
            )

        print("Canonical seed row counts:")

        for table in (
            "canonical_warehouses",
            "canonical_suppliers",
            "canonical_skus",
            "canonical_opening_stock",
            "sales_history",
        ):
            print(f"  {table}: {count_rows(cursor, table):,}")

        cursor.execute(
            f"""
            SELECT COUNT(*)
            FROM {SCHEMA}.inventory
            WHERE sku_id LIKE 'SKU-%'
            """
        )
        print(
            "  canonical operational inventory: "
            f"{cursor.fetchone()[0]:,}"
        )

        connection.commit()
        print("Canonical PostgreSQL seed load completed successfully.")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
        engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Load canonical seed CSV files into PostgreSQL."
    )
    parser.add_argument(
        "--refresh-inventory",
        action="store_true",
        help=(
            "Update existing canonical inventory quantities from opening "
            "stock. Without this flag, existing inventory rows are preserved."
        ),
    )
    args = parser.parse_args()
    load(refresh_inventory=args.refresh_inventory)
