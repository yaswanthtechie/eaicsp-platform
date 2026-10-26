"""Create canonical master data tables for Round 15.

Revision ID: 006_canonical_master_data
Revises: 005_po_hold_source
"""

from alembic import op
import sqlalchemy as sa

revision = "006_canonical_master_data"
down_revision = "005_po_hold_source"
branch_labels = None
depends_on = None


def _schema():
    """Use the inventory schema on PostgreSQL, but not on SQLite."""
    return None if op.get_bind().dialect.name == "sqlite" else "inventory"


def _qualified_table(table_name):
    """Return a schema-aware foreign-key target."""
    schema = _schema()
    if schema:
        return f"{schema}.{table_name}"
    return table_name


def upgrade():
    schema = _schema()

    op.create_table(
        "canonical_warehouses",
        sa.Column("warehouse_id", sa.String(30), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("city", sa.String(100)),
        sa.Column("state", sa.String(100)),
        sa.Column("lat", sa.Float()),
        sa.Column("lng", sa.Float()),
        sa.Column("capacity_units", sa.Integer()),
        sa.Column("demand_weight", sa.Float()),
        schema=schema,
    )

    op.create_table(
        "canonical_suppliers",
        sa.Column("supplier_id", sa.String(30), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("country", sa.String(100)),
        sa.Column("city", sa.String(100)),
        sa.Column("state", sa.String(100)),
        sa.Column("lat", sa.Float()),
        sa.Column("lng", sa.Float()),
        sa.Column(
            "sanctions_flag",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("sanctions_list", sa.String(255)),
        sa.Column("lead_time_days", sa.Integer(), nullable=False),
        sa.Column("payment_terms_days", sa.Integer()),
        sa.Column("reliability_score", sa.Float()),
        schema=schema,
    )

    op.create_table(
        "canonical_skus",
        sa.Column("sku_id", sa.String(30), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("category", sa.String(100)),
        sa.Column("pack_size", sa.Integer()),
        sa.Column("unit_price", sa.Float(), nullable=False),
        sa.Column("unit_cost", sa.Float(), nullable=False),
        sa.Column("abc_class", sa.String(5)),
        sa.Column(
            "supplier_id",
            sa.String(30),
            sa.ForeignKey(
                f"{_qualified_table('canonical_suppliers')}.supplier_id"
            ),
            nullable=False,
        ),
        schema=schema,
    )

    op.create_table(
        "canonical_opening_stock",
        sa.Column("snapshot_date", sa.Date(), primary_key=True),
        sa.Column("sku_id", sa.String(30), primary_key=True),
        sa.Column("warehouse_id", sa.String(30), primary_key=True),
        sa.Column("quantity_on_hand", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["sku_id"],
            [f"{_qualified_table('canonical_skus')}.sku_id"],
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            [f"{_qualified_table('canonical_warehouses')}.warehouse_id"],
        ),
        schema=schema,
    )

    # Store the observed sales price for canonical daily sales records.
    op.add_column(
        "sales_history",
        sa.Column(
            "unit_price",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
        schema=schema,
    )


def downgrade():
    schema = _schema()
    op.drop_column("sales_history", "unit_price", schema=schema)
    op.drop_table("canonical_opening_stock", schema=schema)
    op.drop_table("canonical_skus", schema=schema)
    op.drop_table("canonical_suppliers", schema=schema)
    op.drop_table("canonical_warehouses", schema=schema)