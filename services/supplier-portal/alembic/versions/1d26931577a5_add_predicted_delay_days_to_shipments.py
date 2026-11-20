"""add predicted delay days to shipments

Revision ID: 1d26931577a5
Revises: 008_shipment_eta_events
Create Date: 2026-11-19 17:04:01.130202
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.config import settings

revision: str = "1d26931577a5"
down_revision: Union[str, Sequence[str], None] = "008_shipment_eta_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "shipments",
        sa.Column("predicted_delay_days", sa.Integer(), nullable=True),
        schema=settings.SUPPLIER_DB_SCHEMA,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column(
        "shipments",
        "predicted_delay_days",
        schema=settings.SUPPLIER_DB_SCHEMA,
    )
