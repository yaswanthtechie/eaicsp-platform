"""Add hold_source to purchase_orders

Revision ID: 005_po_hold_source
Revises: 004_compliance_consumer_tables
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "005_po_hold_source"
down_revision: Union[str, None] = "004_compliance_consumer_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    po_columns = [c["name"] for c in inspector.get_columns("purchase_orders")]
    if "hold_source" not in po_columns:
        op.add_column("purchase_orders", sa.Column("hold_source", sa.String(), nullable=True))
    op.execute("UPDATE purchase_orders SET hold_source = 'compliance' WHERE status = 'on_hold'")


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    po_columns = [c["name"] for c in inspector.get_columns("purchase_orders")]
    if "hold_source" in po_columns:
        op.drop_column("purchase_orders", "hold_source")

