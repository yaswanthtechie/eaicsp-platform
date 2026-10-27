"""create shipment eta events

Revision ID: 007_shipment_eta_events
Revises: 006_shipment_details
"""

from alembic import op
import sqlalchemy as sa

from app.core.config import settings


revision = "007_shipment_eta_events"
down_revision = "006_shipment_details"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shipment_eta_events",
        sa.Column("event_id", sa.String(length=36), primary_key=True),
        sa.Column("shipment_id", sa.String(length=20), nullable=False),
        sa.Column(
            "predicted_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        schema=settings.SUPPLIER_DB_SCHEMA,
    )

    op.create_index(
        "ix_shipment_eta_events_shipment_id",
        "shipment_eta_events",
        ["shipment_id"],
        schema=settings.SUPPLIER_DB_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_shipment_eta_events_shipment_id",
        table_name="shipment_eta_events",
        schema=settings.SUPPLIER_DB_SCHEMA,
    )

    op.drop_table(
        "shipment_eta_events",
        schema=settings.SUPPLIER_DB_SCHEMA,
    )