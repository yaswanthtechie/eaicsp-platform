import pytest
from alembic.config import Config
from sqlalchemy import inspect, text

from alembic import command
from tests.conftest import test_engine


def _alembic_config() -> Config:
    cfg = Config("alembic.ini")
    db_url = test_engine.url.render_as_string(hide_password=False).replace("%", "%%")
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _reset_postgres_schema() -> None:
    """Drop and recreate public schema so Alembic runs on a truly empty Postgres DB."""
    if not (test_engine.url.database or "").endswith("_test"):
        raise RuntimeError(
            f"Refusing to wipe non-test database {test_engine.url.database!r}"
        )
    test_engine.dispose()
    with test_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))


@pytest.mark.integration
def test_alembic_migrations_lifecycle():
    """
    Milestone 1 requirement:
    Verify that Alembic migrations run cleanly against the real database,
    supporting upgrade and downgrade without manual DDL.
    """
    if test_engine.dialect.name != "postgresql":
        pytest.skip("Integration test requires PostgreSQL")

    cfg = _alembic_config()
    _reset_postgres_schema()

    # 1. Upgrade clean empty DB to head
    command.upgrade(cfg, "head")

    inspector = inspect(test_engine)
    tables_after_upgrade = inspector.get_table_names()
    expected_tables = [
        "inventory",
        "sales_history",
        "purchase_orders",
        "suppliers",
        "inventory_cost_layers",
    ]
    for table in expected_tables:
        assert table in tables_after_upgrade, (
            f"Expected table {table} after migration upgrade"
        )

    # Verify columns and primary key on inventory
    columns = {col["name"]: col for col in inspector.get_columns("inventory")}
    assert "sku_id" in columns
    assert "warehouse_id" in columns
    assert "version" in columns
    assert "product_name" in columns

    pk = inspector.get_pk_constraint("inventory")
    assert set(pk["constrained_columns"]) == {"sku_id", "warehouse_id"}

    # 2. Downgrade to base
    command.downgrade(cfg, "base")

    inspector = inspect(test_engine)
    tables_after_downgrade = inspector.get_table_names()
    for table in expected_tables:
        assert table not in tables_after_downgrade, (
            f"Table {table} should be dropped after downgrade"
        )

    # 3. Re-upgrade to head
    command.upgrade(cfg, "head")


@pytest.mark.integration
def test_alembic_upgrade_head_inserts_po_on_empty_database():
    """
    Reviewer requirement:
    Verify that running alembic upgrade head on an empty PostgreSQL database
    creates the schema matching the PurchaseOrder model (including approval_status)
    and allows inserting a PurchaseOrder record.
    """
    if test_engine.dialect.name != "postgresql":
        pytest.skip("Integration test requires PostgreSQL")

    from datetime import UTC, datetime

    from sqlalchemy.orm import Session

    from app.models.purchase_order import PurchaseOrder

    cfg = _alembic_config()

    # Reset schema and upgrade clean empty DB to head
    _reset_postgres_schema()
    command.upgrade(cfg, "head")

    inspector = inspect(test_engine)
    po_cols = {col["name"]: col for col in inspector.get_columns("purchase_orders")}
    assert "approval_status" in po_cols, (
        "approval_status must exist in purchase_orders table"
    )

    # Insert a PO using the model
    with Session(test_engine) as session:
        po = PurchaseOrder(
            po_id="PO-2026-000002",
            sku_id="SKU-000002",
            warehouse_id="WH-BLR-01",
            supplier_id="SUP-00002",
            quantity=100,
            unit_cost=12.50,
            expected_cost=1250.00,
            status="draft",
            approval_status="pending_vp_approval",
            created_at=datetime.now(UTC),
        )
        session.add(po)
        session.commit()

        queried = session.query(PurchaseOrder).filter_by(po_id="PO-2026-000002").first()
        assert queried is not None
        assert queried.approval_status == "pending_vp_approval"
