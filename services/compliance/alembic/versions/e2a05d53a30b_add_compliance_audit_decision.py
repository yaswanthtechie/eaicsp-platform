"""add compliance audit decision

Revision ID: e2a05d53a30b
Revises: ad1be0670cf4
Create Date: 2026-09-30 20:50:47.618268

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e2a05d53a30b"
down_revision: Union[str, Sequence[str], None] = "ad1be0670cf4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Add compliance decision to audit records."""

    op.add_column(
        "compliance_audit",
        sa.Column(
            "decision",
            sa.String(),
            nullable=True,
        ),
    )

    op.create_index(
        "idx_audit_decision",
        "compliance_audit",
        ["decision"],
        unique=False,
    )


def downgrade() -> None:
    """Remove compliance decision from audit records."""

    op.drop_index(
        "idx_audit_decision",
        table_name="compliance_audit",
    )

    op.drop_column(
        "compliance_audit",
        "decision",
    )


