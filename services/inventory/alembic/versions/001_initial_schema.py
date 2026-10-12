"""Initial schema for inventory service tables

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-29 22:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. inventory table
    op.create_table(
        'inventory',
        sa.Column('sku_id', sa.String(), nullable=False),
        sa.Column('warehouse_id', sa.String(), nullable=False),
        sa.Column('product_name', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False, server_default='Uncategorized'),
        sa.Column('quantity_on_hand', sa.Integer(), nullable=False),
        sa.Column('avg_daily_demand', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('lead_time_days', sa.Integer(), nullable=False),
        sa.Column('safety_stock', sa.Integer(), nullable=False),
        sa.Column('warehouse_type', sa.String(), nullable=False, server_default='local'),
        sa.Column('parent_warehouse_id', sa.String(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.PrimaryKeyConstraint('sku_id', 'warehouse_id', name='pk_inventory'),
    )

    # 2. sales_history table
    op.create_table(
        'sales_history',
        sa.Column('sku_id', sa.String(), nullable=False),
        sa.Column('warehouse_id', sa.String(), nullable=False),
        sa.Column('sale_date', sa.Date(), nullable=False),
        sa.Column('quantity_sold', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('sku_id', 'warehouse_id', 'sale_date', name='pk_sales_history'),
    )
    op.create_index('ix_sales_history_sale_date', 'sales_history', ['sale_date'])

    # 3. purchase_orders table
    op.create_table(
        'purchase_orders',
        sa.Column('po_id', sa.String(), nullable=False),
        sa.Column('sku_id', sa.String(), nullable=False),
        sa.Column('warehouse_id', sa.String(), nullable=False),
        sa.Column('supplier_id', sa.String(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_cost', sa.Float(), nullable=False),
        sa.Column('expected_cost', sa.Float(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='draft'),
        sa.Column('approval_status', sa.String(), nullable=False, server_default='pending_vp_approval'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('po_id', name='pk_purchase_orders'),
    )
    op.create_index('ix_purchase_orders_po_id', 'purchase_orders', ['po_id'])
    op.create_index('ix_purchase_orders_sku_id', 'purchase_orders', ['sku_id'])
    op.create_index('ix_purchase_orders_warehouse_id', 'purchase_orders', ['warehouse_id'])

    # 4. suppliers table
    op.create_table(
        'suppliers',
        sa.Column('supplier_id', sa.String(), nullable=False),
        sa.Column('supplier_name', sa.String(), nullable=False),
        sa.Column('sku_id', sa.String(), nullable=False),
        sa.Column('unit_cost', sa.Float(), nullable=False),
        sa.Column('lead_time_days', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('supplier_id', name='pk_suppliers'),
    )
    op.create_index('ix_suppliers_supplier_id', 'suppliers', ['supplier_id'])
    op.create_index('ix_suppliers_sku_id', 'suppliers', ['sku_id'])

    # 5. inventory_cost_layers table
    op.create_table(
        'inventory_cost_layers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('sku_id', sa.String(), nullable=False),
        sa.Column('warehouse_id', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('quantity_received', sa.Integer(), nullable=False),
        sa.Column('quantity_remaining', sa.Integer(), nullable=False),
        sa.Column('unit_cost', sa.Float(), nullable=False),
        sa.Column('received_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id', name='pk_inventory_cost_layers'),
    )
    op.create_index('ix_inventory_cost_layers_sku_id', 'inventory_cost_layers', ['sku_id'])
    op.create_index('ix_inventory_cost_layers_warehouse_id', 'inventory_cost_layers', ['warehouse_id'])
    op.create_index('ix_inventory_cost_layers_category', 'inventory_cost_layers', ['category'])
    op.create_index('ix_inventory_cost_layers_received_at', 'inventory_cost_layers', ['received_at'])


def downgrade() -> None:
    op.drop_table('inventory_cost_layers')
    op.drop_table('suppliers')
    op.drop_table('purchase_orders')
    op.drop_table('sales_history')
    op.drop_table('inventory')
