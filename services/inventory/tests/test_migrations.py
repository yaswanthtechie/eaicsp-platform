from sqlalchemy import create_engine, inspect, text

from scripts.migrate_add_approval_status import migrate


def test_approval_status_migration_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")

    # A purchase_orders table as it existed before Round 10.
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE purchase_orders ("
            "po_id VARCHAR PRIMARY KEY, sku_id VARCHAR NOT NULL, "
            "warehouse_id VARCHAR NOT NULL, supplier_id VARCHAR NOT NULL, "
            "quantity INTEGER NOT NULL, unit_cost FLOAT NOT NULL, "
            "expected_cost FLOAT NOT NULL, status VARCHAR NOT NULL, "
            "created_at DATETIME NOT NULL)"
        ))
        connection.execute(text(
            "INSERT INTO purchase_orders VALUES "
            "('PO-OLD', 'SKU1', 'WH1', 'SUP1', 10, 5.0, 50.0, 'draft', "
            "'2026-09-01 00:00:00')"
        ))

    assert migrate(engine) is True
    assert migrate(engine) is False  # second run is a no-op

    columns = {c["name"] for c in inspect(engine).get_columns("purchase_orders")}
    assert "approval_status" in columns

    with engine.connect() as connection:
        status = connection.execute(text(
            "SELECT approval_status FROM purchase_orders WHERE po_id = 'PO-OLD'"
        )).scalar_one()

    # Pre-existing drafts must stay receivable.
    assert status == "approved"
