import pytest
from alembic.config import Config
from alembic import command
from sqlalchemy import inspect
from app.core.config import settings
from tests.conftest import test_engine


@pytest.mark.integration
def test_alembic_migrations_lifecycle():
    """
    Milestone 1 requirement:
    Verify that Alembic migrations run cleanly against the real database,
    supporting upgrade and downgrade without manual DDL.
    """
    if test_engine.dialect.name != "postgresql":
        pytest.skip("Integration test requires PostgreSQL")

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", settings.TEST_DATABASE_URL)

    # 1. Downgrade to base
    command.downgrade(cfg, "base")

    inspector = inspect(test_engine)
    tables_after_downgrade = inspector.get_table_names()
    for table in ["inventory", "sales_history", "purchase_orders", "suppliers", "inventory_cost_layers"]:
        assert table not in tables_after_downgrade, f"Table {table} should be dropped after downgrade"

    # 2. Upgrade to head
    command.upgrade(cfg, "head")

    inspector = inspect(test_engine)
    tables_after_upgrade = inspector.get_table_names()
    expected_tables = ["inventory", "sales_history", "purchase_orders", "suppliers", "inventory_cost_layers"]
    for table in expected_tables:
        assert table in tables_after_upgrade, f"Expected table {table} after migration upgrade"

    # 3. Verify columns and primary key on inventory
    columns = {col["name"]: col for col in inspector.get_columns("inventory")}
    assert "sku_id" in columns
    assert "warehouse_id" in columns
    assert "version" in columns
    assert "product_name" in columns

    pk = inspector.get_pk_constraint("inventory")
    assert set(pk["constrained_columns"]) == {"sku_id", "warehouse_id"}


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

    from sqlalchemy.orm import Session
    from datetime import datetime, UTC
    from app.models.purchase_order import PurchaseOrder

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", settings.TEST_DATABASE_URL)

    # Clean DB and upgrade to head
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")

    inspector = inspect(test_engine)
    po_cols = {col["name"]: col for col in inspector.get_columns("purchase_orders")}
    assert "approval_status" in po_cols, "approval_status must exist in purchase_orders table"

    # Insert a PO using the model
    with Session(test_engine) as session:
        po = PurchaseOrder(
            po_id="PO-MIGRATE-INT-1",
            sku_id="SKU-INT-1",
            warehouse_id="WH-INT-1",
            supplier_id="SUP-INT-1",
            quantity=100,
            unit_cost=12.50,
            expected_cost=1250.00,
            status="draft",
            approval_status="pending_vp_approval",
            created_at=datetime.now(UTC),
        )
        session.add(po)
        session.commit()

        queried = session.query(PurchaseOrder).filter_by(po_id="PO-MIGRATE-INT-1").first()
        assert queried is not None
        assert queried.approval_status == "pending_vp_approval"

