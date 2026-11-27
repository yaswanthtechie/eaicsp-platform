"""Create idempotency_records table

Revision ID: 011_idempotency_records
Revises: 010_stock_reservations
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011_idempotency_records"
down_revision: Union[str, None] = "010_stock_reservations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "idempotency_records" not in tables:
        op.create_table(
            "idempotency_records",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("idempotency_key", sa.String(128), nullable=False),
            sa.Column("scope", sa.String(128), nullable=False),
            sa.Column("request_hash", sa.String(64), nullable=False),
            sa.Column(
                "status",
                sa.String(16),
                nullable=False,
                server_default="IN_PROGRESS",
            ),
            sa.Column("response_status_code", sa.Integer(), nullable=True),
            sa.Column("response_body", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint(
                "idempotency_key",
                "scope",
                name="uq_idempotency_key_scope",
            ),
            sa.CheckConstraint(
                "status IN ('IN_PROGRESS', 'COMPLETED')",
                name="ck_idempotency_records_status",
            ),
        )
        op.create_index(
            "ix_idempotency_records_expires_at",
            "idempotency_records",
            ["expires_at"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "idempotency_records" in tables:
        op.drop_index(
            "ix_idempotency_records_expires_at",
            table_name="idempotency_records",
        )
        op.drop_table("idempotency_records")
