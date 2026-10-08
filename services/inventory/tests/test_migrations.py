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


def test_alembic_upgrade_head_creates_matching_schema_and_allows_po_insert(tmp_path):
    """
    Reviewer requirement:
    Verify that alembic upgrade head creates the matching schema
    (including approval_status) and allows inserting a PO on an empty database.
    """
    from alembic.config import Config
    from alembic import command
    from sqlalchemy.orm import Session
    from datetime import datetime, UTC
    from app.models.purchase_order import PurchaseOrder

    db_file = tmp_path / "test_fresh_upgrade.db"
    db_url = f"sqlite:///{db_file}"

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    command.upgrade(alembic_cfg, "head")

    test_engine = create_engine(db_url)
    inspector = inspect(test_engine)
    columns = {c["name"] for c in inspector.get_columns("purchase_orders")}
    assert "approval_status" in columns, "approval_status column must exist in purchase_orders"
    assert "hold_reason" in columns, "hold_reason column must exist in purchase_orders"

    tables = set(inspector.get_table_names())
    assert "processed_events" in tables, "processed_events table must exist"
    assert "supplier_compliance_states" in tables, "supplier_compliance_states table must exist"

    with Session(test_engine) as session:
        po = PurchaseOrder(
            po_id="PO-TEST-001",
            sku_id="SKU-1",
            warehouse_id="WH-1",
            supplier_id="SUP-1",
            quantity=10,
            unit_cost=15.0,
            expected_cost=150.0,
            status="on_hold",
            approval_status="pending_vp_approval",
            hold_reason="Supplier moved to BLOCK",
            created_at=datetime.now(UTC),
        )
        session.add(po)
        session.commit()

        queried = session.query(PurchaseOrder).filter_by(po_id="PO-TEST-001").first()
        assert queried is not None
        assert queried.approval_status == "pending_vp_approval"
        assert queried.status == "on_hold"
        assert queried.hold_reason == "Supplier moved to BLOCK"

