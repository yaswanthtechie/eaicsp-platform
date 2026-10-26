"""Create products and warehouses tables for canonical master data

Revision ID: 006_create_products_and_warehouses_tables
Revises: 005_po_hold_source
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "006_create_products_and_warehouses_tables"
down_revision: Union[str, None] = "005_po_hold_source"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "products" not in tables:
        op.create_table(
            "products",
            sa.Column("sku_id", sa.String(16), primary_key=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("category", sa.String(64), nullable=False),
            sa.Column("pack_size", sa.String(64), nullable=True),
            sa.Column("unit_price", sa.Float(), nullable=False),
            sa.Column("unit_cost", sa.Float(), nullable=False),
            sa.Column("abc_class", sa.String(8), nullable=True),
            sa.Column("supplier_id", sa.String(16), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_products_supplier_id", "products", ["supplier_id"])

    if "warehouses" not in tables:
        op.create_table(
            "warehouses",
            sa.Column("warehouse_id", sa.String(16), primary_key=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("city", sa.String(64), nullable=False),
            sa.Column("state", sa.String(64), nullable=False),
            sa.Column("lat", sa.Float(), nullable=True),
            sa.Column("lng", sa.Float(), nullable=True),
            sa.Column("capacity_units", sa.Integer(), nullable=False),
            sa.Column("demand_weight", sa.Float(), nullable=False, server_default="1.0"),
            sa.Column("warehouse_type", sa.String(32), nullable=False, server_default="central"),
            sa.Column("parent_warehouse_id", sa.String(16), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table("warehouses")
    op.drop_index("ix_products_supplier_id", table_name="products")
    op.drop_table("products")
