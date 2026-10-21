
"""Store canonical SKU pack_size as text.

Revision ID: 007_pack_size_text
Revises: 006_canonical_master_data
"""

from alembic import op
import sqlalchemy as sa

revision = "007_pack_size_text"
down_revision = "006_canonical_master_data"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "canonical_skus",
        "pack_size",
        schema="inventory",
        existing_type=sa.Integer(),
        type_=sa.String(length=50),
        existing_nullable=True,
        postgresql_using="pack_size::text",
    )


def downgrade():
    op.alter_column(
        "canonical_skus",
        "pack_size",
        schema="inventory",
        existing_type=sa.String(length=50),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="NULLIF(pack_size, '')::integer",
    )
