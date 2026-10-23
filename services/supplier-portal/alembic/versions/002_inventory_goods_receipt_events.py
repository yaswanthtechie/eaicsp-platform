
from alembic import op
import sqlalchemy as sa

from app.core.config import settings

revision = "002_inventory_goods_receipt_events"
down_revision = "001_suppliers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = settings.SUPPLIER_DB_SCHEMA

    op.create_table(
        "inventory_goods_receipt_events",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("receipt_id", sa.String(32), nullable=False),
        sa.Column("po_id", sa.String(32), nullable=False),
        sa.Column("supplier_id", sa.String(9), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        schema=schema,
    )

    op.create_index(
        "ix_inventory_goods_receipt_events_receipt_id",
        "inventory_goods_receipt_events",
        ["receipt_id"],
        schema=schema,
    )
    op.create_index(
        "ix_inventory_goods_receipt_events_po_id",
        "inventory_goods_receipt_events",
        ["po_id"],
        schema=schema,
    )
    op.create_index(
        "ix_inventory_goods_receipt_events_supplier_id",
        "inventory_goods_receipt_events",
        ["supplier_id"],
        schema=schema,
    )


def downgrade() -> None:
    schema = settings.SUPPLIER_DB_SCHEMA

    op.drop_index(
        "ix_inventory_goods_receipt_events_supplier_id",
        table_name="inventory_goods_receipt_events",
        schema=schema,
    )
    op.drop_index(
        "ix_inventory_goods_receipt_events_po_id",
        table_name="inventory_goods_receipt_events",
        schema=schema,
    )
    op.drop_index(
        "ix_inventory_goods_receipt_events_receipt_id",
        table_name="inventory_goods_receipt_events",
        schema=schema,
    )
    op.drop_table(
        "inventory_goods_receipt_events",
        schema=schema,
    )
