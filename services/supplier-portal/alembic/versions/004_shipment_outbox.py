
from alembic import op
import sqlalchemy as sa

from app.core.config import settings

revision = "004_shipment_outbox"
down_revision = "003_po_ack_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = settings.SUPPLIER_DB_SCHEMA

    op.create_table(
        "shipment_outbox",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("topic", sa.String(200), nullable=False),
        sa.Column("message_key", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("last_error", sa.String(1000), nullable=True),
        schema=schema,
    )

    op.create_index(
        "ix_shipment_outbox_status_created_at",
        "shipment_outbox",
        ["status", "created_at"],
        unique=False,
        schema=schema,
    )


def downgrade() -> None:
    schema = settings.SUPPLIER_DB_SCHEMA

    op.drop_index(
        "ix_shipment_outbox_status_created_at",
        table_name="shipment_outbox",
        schema=schema,
    )
    op.drop_table("shipment_outbox", schema=schema)
