"""Create outbox table for transactional outbox pattern

Revision ID: 002_create_outbox_table
Revises: 001_initial_schema
Create Date: 2026-09-30 12:18:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_create_outbox_table'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'outbox',
        sa.Column('id', sa.String(), primary_key=True, nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('aggregate_type', sa.String(), nullable=False),
        sa.Column('aggregate_id', sa.String(), nullable=False),
        sa.Column('payload', sa.Text(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='PENDING'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id', name='pk_outbox'),
    )
    op.create_index('ix_outbox_event_type', 'outbox', ['event_type'])
    op.create_index('ix_outbox_aggregate_id', 'outbox', ['aggregate_id'])
    op.create_index('ix_outbox_status', 'outbox', ['status'])
    op.create_index('ix_outbox_created_at', 'outbox', ['created_at'])


def downgrade() -> None:
    op.drop_table('outbox')
