
from alembic import op
import sqlalchemy as sa

from app.core.config import settings

revision = "001_suppliers"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = settings.SUPPLIER_DB_SCHEMA

    # Create the PostgreSQL schema before creating its table.
    op.execute(
        sa.text(
            f'CREATE SCHEMA IF NOT EXISTS "{schema}"'
        )
    )

    op.create_table(
        "suppliers",
        sa.Column("supplier_id", sa.String(9), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("state", sa.String(100), nullable=False),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column(
            "sanctions_flag",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("sanctions_list", sa.String(100), nullable=True),
        sa.Column("lead_time_days", sa.Integer(), nullable=False),
        sa.Column("payment_terms_days", sa.Integer(), nullable=False),
        sa.Column("reliability_score", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        schema=schema,
    )


def downgrade() -> None:
    op.drop_table(
        "suppliers",
        schema=settings.SUPPLIER_DB_SCHEMA,
    )
