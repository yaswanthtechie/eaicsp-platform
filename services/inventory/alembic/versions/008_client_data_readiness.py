"""Add client-data readiness columns and supplier_lead_times table

Revision ID: 008_client_data_readiness
Revises: 007_create_goods_receipts_tables
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008_client_data_readiness"
down_revision: Union[str, None] = "007_create_goods_receipts_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "products" in tables:
        product_cols = {col["name"] for col in inspector.get_columns("products")}
        if "unit_of_measure" not in product_cols:
            op.add_column(
                "products",
                sa.Column("unit_of_measure", sa.String(32), nullable=True),
            )
        if "is_active" not in product_cols:
            op.add_column(
                "products",
                sa.Column(
                    "is_active",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.true(),
                ),
            )

    if "warehouses" in tables:
        warehouse_cols = {col["name"] for col in inspector.get_columns("warehouses")}
        if "country" not in warehouse_cols:
            op.add_column(
                "warehouses",
                sa.Column(
                    "country",
                    sa.String(64),
                    nullable=False,
                    server_default="India",
                ),
            )
        if "pincode" not in warehouse_cols:
            op.add_column(
                "warehouses",
                sa.Column("pincode", sa.String(16), nullable=True),
            )

    if "supplier_lead_times" not in tables:
        op.create_table(
            "supplier_lead_times",
            sa.Column(
                "supplier_id",
                sa.String(16),
                sa.ForeignKey("suppliers.supplier_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "sku_id",
                sa.String(16),
                sa.ForeignKey("products.sku_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("average_lead_time_days", sa.Integer(), nullable=False),
            sa.Column("minimum_lead_time_days", sa.Integer(), nullable=True),
            sa.Column("maximum_lead_time_days", sa.Integer(), nullable=True),
            sa.Column("effective_date", sa.Date(), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint(
                "supplier_id",
                "sku_id",
                name="pk_supplier_lead_times",
            ),
        )
        op.create_index(
            "ix_supplier_lead_times_supplier_id",
            "supplier_lead_times",
            ["supplier_id"],
        )
        op.create_index(
            "ix_supplier_lead_times_sku_id",
            "supplier_lead_times",
            ["sku_id"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "supplier_lead_times" in tables:
        op.drop_table("supplier_lead_times")

    if "warehouses" in tables:
        warehouse_cols = {col["name"] for col in inspector.get_columns("warehouses")}
        if "pincode" in warehouse_cols:
            op.drop_column("warehouses", "pincode")
        if "country" in warehouse_cols:
            op.drop_column("warehouses", "country")

    if "products" in tables:
        product_cols = {col["name"] for col in inspector.get_columns("products")}
        if "is_active" in product_cols:
            op.drop_column("products", "is_active")
        if "unit_of_measure" in product_cols:
            op.drop_column("products", "unit_of_measure")
