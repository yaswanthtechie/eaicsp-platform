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
