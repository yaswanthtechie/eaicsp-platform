"""Create goods receipts and goods receipt items tables

Revision ID: 006_create_goods_receipts_tables
Revises: 005_po_hold_source
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "006_create_goods_receipts_tables"
down_revision: Union[str, None] = "005_po_hold_source"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "goods_receipts" not in tables:
        op.create_table(
            "goods_receipts",
            sa.Column("receipt_id", sa.String(32), primary_key=True),
            sa.Column("po_id", sa.String(32), nullable=False),
            sa.Column("supplier_id", sa.String(32), nullable=False),
            sa.Column("warehouse_id", sa.String(32), nullable=False),
            sa.Column("received_by", sa.String(128), nullable=False),
            sa.Column("received_at", sa.DateTime(), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="received"),
            sa.Column("notes", sa.Text(), nullable=True),
        )
        op.create_index("ix_goods_receipts_po_id", "goods_receipts", ["po_id"])
        op.create_index("ix_goods_receipts_supplier_id", "goods_receipts", ["supplier_id"])
        op.create_index("ix_goods_receipts_warehouse_id", "goods_receipts", ["warehouse_id"])

    if "goods_receipt_items" not in tables:
        op.create_table(
            "goods_receipt_items",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "receipt_id",
                sa.String(32),
                sa.ForeignKey("goods_receipts.receipt_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("sku_id", sa.String(32), nullable=False),
            sa.Column("quantity_received", sa.Integer(), nullable=False),
            sa.Column("unit_cost", sa.Float(), nullable=True),
        )
        op.create_index("ix_goods_receipt_items_receipt_id", "goods_receipt_items", ["receipt_id"])
        op.create_index("ix_goods_receipt_items_sku_id", "goods_receipt_items", ["sku_id"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "goods_receipt_items" in tables:
        op.drop_table("goods_receipt_items")
    if "goods_receipts" in tables:
        op.drop_table("goods_receipts")

