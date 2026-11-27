"""Add reserved_quantity to inventory and create stock_reservations table

Revision ID: 010_stock_reservations
Revises: 009_snapshot_po_history
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010_stock_reservations"
down_revision: Union[str, None] = "009_snapshot_po_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "inventory" in tables:
        inventory_cols = {col["name"] for col in inspector.get_columns("inventory")}
        existing_checks = {
            ck.get("name") for ck in inspector.get_check_constraints("inventory")
        }
        needs_col = "reserved_quantity" not in inventory_cols
        needs_ck = "ck_inventory_reserved_quantity_non_negative" not in existing_checks

        if needs_col or needs_ck:
            with op.batch_alter_table("inventory") as batch_op:
                if needs_col:
                    batch_op.add_column(
                        sa.Column(
                            "reserved_quantity",
                            sa.Integer(),
                            nullable=False,
                            server_default="0",
                        )
                    )
                if needs_ck:
                    batch_op.create_check_constraint(
                        "ck_inventory_reserved_quantity_non_negative",
                        "reserved_quantity >= 0",
                    )

    if "stock_reservations" not in tables:
        op.create_table(
            "stock_reservations",
            sa.Column("reservation_id", sa.String(64), primary_key=True),
            sa.Column("sku_id", sa.String(), nullable=False),
            sa.Column("warehouse_id", sa.String(), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column(
                "status",
                sa.String(16),
                nullable=False,
                server_default="ACTIVE",
            ),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                ["sku_id", "warehouse_id"],
                ["inventory.sku_id", "inventory.warehouse_id"],
                ondelete="CASCADE",
                name="fk_stock_reservations_inventory",
            ),
            sa.CheckConstraint(
                "quantity > 0",
                name="ck_stock_reservations_quantity_positive",
            ),
            sa.CheckConstraint(
                "status IN ('ACTIVE', 'COMMITTED', 'RELEASED', 'EXPIRED')",
                name="ck_stock_reservations_status",
            ),
        )
        op.create_index(
            "ix_stock_reservations_sku_warehouse_status",
            "stock_reservations",
            ["sku_id", "warehouse_id", "status"],
        )
        op.create_index(
            "ix_stock_reservations_status_expires_at",
            "stock_reservations",
            ["status", "expires_at"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "stock_reservations" in tables:
        op.drop_index(
            "ix_stock_reservations_status_expires_at",
            table_name="stock_reservations",
        )
        op.drop_index(
            "ix_stock_reservations_sku_warehouse_status",
            table_name="stock_reservations",
        )
        op.drop_table("stock_reservations")

    if "inventory" in tables:
        inventory_cols = {col["name"] for col in inspector.get_columns("inventory")}
        existing_checks = {
            ck.get("name") for ck in inspector.get_check_constraints("inventory")
        }
        has_col = "reserved_quantity" in inventory_cols
        has_ck = "ck_inventory_reserved_quantity_non_negative" in existing_checks

        if has_col or has_ck:
            with op.batch_alter_table("inventory") as batch_op:
                if has_ck:
                    batch_op.drop_constraint(
                        "ck_inventory_reserved_quantity_non_negative",
                        type_="check",
                    )
                if has_col:
                    batch_op.drop_column("reserved_quantity")
