"""Add client snapshot and purchase-order history columns

Revision ID: 009_snapshot_po_history
Revises: 008_client_data_readiness
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009_snapshot_po_history"
down_revision: Union[str, None] = "008_client_data_readiness"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "inventory" in tables:
        inventory_cols = {col["name"] for col in inspector.get_columns("inventory")}
        if "reorder_point" not in inventory_cols:
            op.add_column(
                "inventory",
                sa.Column("reorder_point", sa.Integer(), nullable=True),
            )

    if "purchase_orders" in tables:
        po_cols = {col["name"] for col in inspector.get_columns("purchase_orders")}
        if "order_date" not in po_cols:
            op.add_column(
                "purchase_orders",
                sa.Column("order_date", sa.Date(), nullable=True),
            )
        if "expected_date" not in po_cols:
            op.add_column(
                "purchase_orders",
                sa.Column("expected_date", sa.Date(), nullable=True),
            )
        if "received_date" not in po_cols:
            op.add_column(
                "purchase_orders",
                sa.Column("received_date", sa.Date(), nullable=True),
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "purchase_orders" in tables:
        po_cols = {col["name"] for col in inspector.get_columns("purchase_orders")}
        if "received_date" in po_cols:
            op.drop_column("purchase_orders", "received_date")
        if "expected_date" in po_cols:
            op.drop_column("purchase_orders", "expected_date")
        if "order_date" in po_cols:
            op.drop_column("purchase_orders", "order_date")

    if "inventory" in tables:
        inventory_cols = {col["name"] for col in inspector.get_columns("inventory")}
        if "reorder_point" in inventory_cols:
            op.drop_column("inventory", "reorder_point")
