"""Add approval_status to purchase_orders

Revision ID: 003_add_approval_status
Revises: 002_create_outbox_table
Create Date: 2026-10-05 13:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_add_approval_status'
down_revision: Union[str, None] = '002_create_outbox_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('purchase_orders')]
    if 'approval_status' not in columns:
        op.add_column(
            'purchase_orders',
            sa.Column('approval_status', sa.String(), nullable=False, server_default='pending_vp_approval'),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('purchase_orders')]
    if 'approval_status' in columns:
        op.drop_column('purchase_orders', 'approval_status')
