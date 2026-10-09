"""Add compliance consumer tables and hold_reason to purchase_orders

Revision ID: 004_compliance_consumer_tables
Revises: 003_add_approval_status
Create Date: 2026-10-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_compliance_consumer_tables'
down_revision: Union[str, None] = '003_add_approval_status'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # 1. Add hold_reason to purchase_orders if not present
    po_columns = [c['name'] for c in inspector.get_columns('purchase_orders')]
    if 'hold_reason' not in po_columns:
        op.add_column(
            'purchase_orders',
            sa.Column('hold_reason', sa.String(), nullable=True),
        )

    # 2. Create processed_events table if not exists
    tables = inspector.get_table_names()
    if 'processed_events' not in tables:
        op.create_table(
            'processed_events',
            sa.Column('event_id', sa.String(), primary_key=True),
            sa.Column('event_type', sa.String(), nullable=False),
            sa.Column('supplier_id', sa.String(), nullable=True),
            sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('processed_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('status', sa.String(), nullable=False, server_default='PROCESSED'),
        )
        op.create_index('ix_processed_events_event_id', 'processed_events', ['event_id'])
        op.create_index('ix_processed_events_event_type', 'processed_events', ['event_type'])
        op.create_index('ix_processed_events_supplier_id', 'processed_events', ['supplier_id'])

    # 3. Create supplier_compliance_states table if not exists
    if 'supplier_compliance_states' not in tables:
        op.create_table(
            'supplier_compliance_states',
            sa.Column('supplier_id', sa.String(), primary_key=True),
            sa.Column('last_status', sa.String(), nullable=False),
            sa.Column('last_occurred_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('last_event_id', sa.String(), nullable=True),
            sa.Column('last_reason', sa.String(), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('ix_supplier_compliance_states_supplier_id', 'supplier_compliance_states', ['supplier_id'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'supplier_compliance_states' in tables:
        op.drop_table('supplier_compliance_states')

    if 'processed_events' in tables:
        op.drop_table('processed_events')

    po_columns = [c['name'] for c in inspector.get_columns('purchase_orders')]
    if 'hold_reason' in po_columns:
        op.drop_column('purchase_orders', 'hold_reason')

