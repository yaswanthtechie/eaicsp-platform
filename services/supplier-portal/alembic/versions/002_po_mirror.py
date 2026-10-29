from alembic import op
import sqlalchemy as sa

from app.core.config import settings

revision = "002_po_mirror"
down_revision = "001_suppliers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = settings.SUPPLIER_DB_SCHEMA

    op.create_table(
        "po_mirror",
        sa.Column("po_id", sa.String(20), primary_key=True),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("po_number", sa.String(30), nullable=True),
        sa.Column("supplier_id", sa.String(9), nullable=False),
        sa.Column("warehouse_id", sa.String(10), nullable=False),
        sa.Column("approval_status", sa.String(20), nullable=False),
        sa.Column("approved_by", sa.String(36), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
        sa.Column("lines", sa.JSON(), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trace_id", sa.String(100), nullable=True),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="approved",
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("event_id", name="uq_po_mirror_event_id"),
        schema=schema,
    )

    op.create_index(
        "ix_supplier_portal_po_mirror_supplier_id",
        "po_mirror",
        ["supplier_id"],
        unique=False,
        schema=schema,
    )


def downgrade() -> None:
    schema = settings.SUPPLIER_DB_SCHEMA
    op.drop_index(
        "ix_supplier_portal_po_mirror_supplier_id",
        table_name="po_mirror",
        schema=schema,
    )
    op.drop_table("po_mirror", schema=schema)

