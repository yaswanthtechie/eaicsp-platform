from alembic import op
import sqlalchemy as sa

from app.core.config import settings

revision = "006_create_shipments"
down_revision = "005_shipment_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = settings.SUPPLIER_DB_SCHEMA

    op.create_table(
        "shipments",
        sa.Column("shipment_id", sa.String(20), primary_key=True),
        sa.Column("po_number", sa.String(30), nullable=False),
        sa.Column("supplier_id", sa.String(9), nullable=False),
        sa.Column("origin", sa.String(255), nullable=False),
        sa.Column("destination_warehouse", sa.String(10), nullable=False),
        sa.Column("carrier", sa.String(255), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("eta_days", sa.Float(), nullable=True),
        sa.Column("confidence_low", sa.Float(), nullable=True),
        sa.Column("confidence_high", sa.Float(), nullable=True),
        sa.Column("model_version", sa.String(100), nullable=True),
        sa.Column("predicted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("top_features", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        schema=schema,
    )

    op.create_index(
        "ix_shipments_po_number",
        "shipments",
        ["po_number"],
        unique=False,
        schema=schema,
    )
    op.create_index(
        "ix_shipments_supplier_id",
        "shipments",
        ["supplier_id"],
        unique=False,
        schema=schema,
    )


def downgrade() -> None:
    schema = settings.SUPPLIER_DB_SCHEMA

    op.drop_index(
        "ix_shipments_supplier_id",
        table_name="shipments",
        schema=schema,
    )
    op.drop_index(
        "ix_shipments_po_number",
        table_name="shipments",
        schema=schema,
    )
    op.drop_table("shipments", schema=schema)
