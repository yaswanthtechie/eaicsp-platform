from alembic import op
import sqlalchemy as sa

from app.core.config import settings

revision = "007_shipment_details"
down_revision = "006_create_shipments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = settings.SUPPLIER_DB_SCHEMA

    op.add_column(
        "shipments",
        sa.Column("shipment_date", sa.Date(), nullable=True),
        schema=schema,
    )
    op.add_column(
        "shipments",
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
        schema=schema,
    )
    op.add_column(
        "shipments",
        sa.Column("tracking_number", sa.String(100), nullable=True),
        schema=schema,
    )
    op.add_column(
        "shipments",
        sa.Column("items", sa.JSON(), nullable=True),
        schema=schema,
    )
    op.add_column(
        "shipments",
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="created",
        ),
        schema=schema,
    )
    op.add_column(
        "shipments",
        sa.Column("created_by", sa.String(100), nullable=True),
        schema=schema,
    )

    op.alter_column(
        "shipments",
        "eta_days",
        existing_type=sa.Integer(),
        type_=sa.Float(),
        schema=schema,
    )
    op.alter_column(
        "shipments",
        "confidence_low",
        existing_type=sa.Integer(),
        type_=sa.Float(),
        schema=schema,
    )
    op.alter_column(
        "shipments",
        "confidence_high",
        existing_type=sa.Integer(),
        type_=sa.Float(),
        schema=schema,
    )


def downgrade() -> None:
    schema = settings.SUPPLIER_DB_SCHEMA

    op.alter_column(
        "shipments",
        "confidence_high",
        existing_type=sa.Float(),
        type_=sa.Integer(),
        schema=schema,
    )
    op.alter_column(
        "shipments",
        "confidence_low",
        existing_type=sa.Float(),
        type_=sa.Integer(),
        schema=schema,
    )
    op.alter_column(
        "shipments",
        "eta_days",
        existing_type=sa.Float(),
        type_=sa.Integer(),
        schema=schema,
    )

    for column in (
        "created_by",
        "status",
        "items",
        "tracking_number",
        "expected_delivery_date",
        "shipment_date",
    ):
        op.drop_column("shipments", column, schema=schema)
