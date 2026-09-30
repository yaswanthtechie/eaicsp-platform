"""
One-off migration for Round 10: add purchase_orders.approval_status.

Base.metadata.create_all() only creates missing tables; it never adds
a column to a table that already exists. Databases created before
Round 10 need this column added once.

Existing POs are marked 'approved' so drafts created before the
approval workflow existed are not retroactively stuck waiting for
VP Operations.

Safe to run more than once.

Usage (from services/inventory):
    python -m scripts.migrate_add_approval_status
"""

from sqlalchemy import inspect, text

from app.database import engine


def migrate(target_engine=engine) -> bool:
    """Add the column if missing. Returns True when it was added."""

    inspector = inspect(target_engine)

    if not inspector.has_table("purchase_orders"):
        return False

    columns = {
        column["name"]
        for column in inspector.get_columns("purchase_orders")
    }

    if "approval_status" in columns:
        return False

    with target_engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE purchase_orders "
                "ADD COLUMN approval_status VARCHAR "
                "NOT NULL DEFAULT 'approved'"
            )
        )

    return True


if __name__ == "__main__":
    if migrate():
        print("Added purchase_orders.approval_status")
    else:
        print("Nothing to do: column already exists or table missing")
