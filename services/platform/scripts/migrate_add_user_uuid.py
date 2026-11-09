"""Safe, idempotent migration to add and backfill `user_uuid` on the `users` table.

Supports PostgreSQL and SQLite.
Safe to rerun multiple times.

Usage:
    python scripts/migrate_add_user_uuid.py
"""

from __future__ import annotations

import re
import sys
import uuid
from pathlib import Path

# Ensure services/platform is on sys.path when script is run standalone
current_dir = Path(__file__).resolve().parent
platform_dir = current_dir.parent
if str(platform_dir) not in sys.path:
    sys.path.insert(0, str(platform_dir))

import sqlalchemy as sa  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402

from app.database import engine as default_engine  # noqa: E402
from app.seed import DEMO_USER_UUIDS  # noqa: E402


def run_migration(engine: Engine | None = None) -> dict[str, int]:
    """Execute the user_uuid migration against the given engine.

    Returns a summary dict with counts of columns added, users backfilled,
    and indices created.
    """
    if engine is None:
        engine = default_engine

    dialect_name = engine.dialect.name
    if dialect_name not in ("sqlite", "postgresql"):
        raise RuntimeError(
            f"Unsupported database dialect: '{dialect_name}'. Only 'sqlite' and 'postgresql' are supported."
        )
    print(f"Running user_uuid migration on {dialect_name} database...")

    summary = {
        "column_added": 0,
        "users_backfilled": 0,
        "index_created": 0,
    }

    inspector = sa.inspect(engine)
    if not inspector.has_table("users"):
        print("Table 'users' does not exist yet. Skipping column migration.")
        return summary

    columns = [col["name"] for col in inspector.get_columns("users")]

    # 1. Add nullable user_uuid column if not present
    if "user_uuid" not in columns:
        print("Adding 'user_uuid' column to 'users' table...")
        with engine.begin() as conn:
            if dialect_name == "postgresql":
                conn.execute(text("ALTER TABLE users ADD COLUMN user_uuid UUID;"))
            else:
                # SQLite: CHAR(32) provides TEXT affinity, matching SQLAlchemy's Uuid(as_uuid=True)
                conn.execute(text("ALTER TABLE users ADD COLUMN user_uuid CHAR(32);"))
        summary["column_added"] = 1
        print("Column 'user_uuid' added successfully.")
    else:
        print("Column 'user_uuid' already exists.")

    # 2. Backfill existing rows missing user_uuid
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT id, email FROM users WHERE user_uuid IS NULL;")
        )
        users_to_backfill = result.fetchall()

        if users_to_backfill:
            print(f"Backfilling {len(users_to_backfill)} user(s) with user_uuid...")
            for user_id, email in users_to_backfill:
                normalized_email = (email or "").lower()
                user_uuid = DEMO_USER_UUIDS.get(normalized_email)
                if user_uuid is None:
                    user_uuid = uuid.uuid4()

                if dialect_name == "postgresql":
                    conn.execute(
                        text(
                            "UPDATE users SET user_uuid = :uuid_val WHERE id = :user_id;"
                        ),
                        {"uuid_val": str(user_uuid), "user_id": user_id},
                    )
                else:
                    # SQLite: store 32-hex string
                    conn.execute(
                        text(
                            "UPDATE users SET user_uuid = :uuid_val WHERE id = :user_id;"
                        ),
                        {"uuid_val": user_uuid.hex, "user_id": user_id},
                    )
            summary["users_backfilled"] = len(users_to_backfill)
            print(f"Backfilled {len(users_to_backfill)} user(s).")
        else:
            print("No users require backfilling.")

    # 3. Create unique index ix_users_user_uuid if not already present
    indexes = [idx["name"] for idx in inspector.get_indexes("users")]
    if "ix_users_user_uuid" not in indexes:
        print("Creating unique index 'ix_users_user_uuid'...")
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_user_uuid "
                    "ON users (user_uuid);"
                )
            )
        summary["index_created"] = 1
        print("Unique index 'ix_users_user_uuid' created.")
    else:
        print("Unique index 'ix_users_user_uuid' already exists.")

    # 4. Enforce NOT NULL constraint
    if dialect_name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ALTER COLUMN user_uuid SET NOT NULL;"))
        print("Enforced NOT NULL constraint on PostgreSQL 'user_uuid'.")
    elif dialect_name == "sqlite":
        with engine.connect() as conn:
            col_info = conn.execute(text("PRAGMA table_info(users);")).fetchall()
            user_uuid_col = next((c for c in col_info if c[1] == "user_uuid"), None)
            needs_rebuild = user_uuid_col is not None and user_uuid_col[3] == 0
            fk_enabled = bool(conn.execute(text("PRAGMA foreign_keys;")).scalar())
            conn.commit()

            if needs_rebuild:
                print(
                    "Enforcing NOT NULL constraint on SQLite 'user_uuid' via safe table rebuild..."
                )
                raw_conn = getattr(conn, "connection", None)
                orig_isolation = getattr(raw_conn, "isolation_level", None)
                try:
                    if raw_conn is not None and orig_isolation is not None:
                        raw_conn.isolation_level = None
                    if fk_enabled:
                        conn.execute(text("PRAGMA foreign_keys = OFF;"))
                    conn.execute(text("BEGIN;"))
                    try:
                        _rebuild_sqlite_users_table(conn)
                        conn.execute(text("COMMIT;"))
                        print("Safe SQLite table rebuild completed successfully.")
                    except Exception:
                        conn.execute(text("ROLLBACK;"))
                        raise
                finally:
                    if fk_enabled:
                        conn.execute(text("PRAGMA foreign_keys = ON;"))
                    if raw_conn is not None and orig_isolation is not None:
                        raw_conn.isolation_level = orig_isolation
            else:
                print("NOT NULL constraint already enforced on SQLite 'user_uuid'.")

    print(f"Migration completed successfully: {summary}")
    return summary


def _rebuild_sqlite_users_table(conn: sa.Connection) -> None:
    """Safely rebuild the SQLite `users` table to enforce NOT NULL on user_uuid.

    Preserves the complete original schema including column types, nullability,
    primary keys, AUTOINCREMENT, defaults, unique constraints, foreign keys,
    CHECK constraints, collations, indexes, triggers, and generated columns.
    """
    # 1. Fetch original table DDL from sqlite_master
    orig_ddl = conn.execute(
        text("SELECT sql FROM sqlite_master WHERE type='table' AND name='users';")
    ).scalar()
    if not orig_ddl:
        raise RuntimeError("Table 'users' not found in sqlite_master")

    # 2. Fetch existing triggers and explicit indexes
    triggers = conn.execute(
        text(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type='trigger' AND tbl_name='users' AND sql IS NOT NULL;"
        )
    ).fetchall()
    indexes = conn.execute(
        text(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type='index' AND tbl_name='users' AND sql IS NOT NULL;"
        )
    ).fetchall()

    # 3. Identify non-generated columns for the data copy step
    table_xinfo = conn.execute(text("PRAGMA table_xinfo(users);")).fetchall()
    # table_xinfo tuple: (cid, name, type, notnull, dflt_value, pk, hidden)
    # hidden: 0 = normal column, 1 = hidden column, 2 = virtual generated, 3 = stored generated
    insertable_cols = [col[1] for col in table_xinfo if col[6] in (0, 1)]

    # 4. Construct users_migration_new DDL preserving the full original schema:
    header_pattern = r"(?i)^\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:\"users\"|'users'|\[users\]|users)\s*\("
    match = re.search(header_pattern, orig_ddl)
    if not match:
        raise RuntimeError(
            f"Could not parse CREATE TABLE header in original DDL: {orig_ddl}"
        )

    new_ddl = "CREATE TABLE users_migration_new (" + orig_ddl[match.end() :]

    # Enforce NOT NULL on user_uuid in the DDL if absent
    uuid_col_pattern = r"(?i)([(,]\s*)([\"`'\[]?user_uuid[\"`'\]]?\s+[A-Za-z]+(?:\s*\(\s*\d+(?:\s*,\s*\d+)?\s*\))?)([^,]*)"

    def _add_not_null(m: re.Match[str]) -> str:
        prefix = m.group(1)
        col_and_type = m.group(2)
        rest = m.group(3)
        if not re.search(r"\bNOT\s+NULL\b", rest, flags=re.IGNORECASE):
            return f"{prefix}{col_and_type} NOT NULL{rest}"
        return f"{prefix}{col_and_type}{rest}"

    new_ddl, count = re.subn(uuid_col_pattern, _add_not_null, new_ddl, count=1)
    if count == 0:
        raise RuntimeError("Could not find user_uuid column definition in original DDL")

    # 5. Execute table swap inside the caller's transaction
    cols_joined = ", ".join(insertable_cols)
    conn.execute(text(new_ddl))
    conn.execute(
        text(
            f"INSERT INTO users_migration_new ({cols_joined}) "
            f"SELECT {cols_joined} FROM users;"
        )
    )
    conn.execute(text("DROP TABLE users;"))
    conn.execute(text("ALTER TABLE users_migration_new RENAME TO users;"))

    # 6. Recreate indexes
    for _name, sql in indexes:
        if sql:
            create_sql = sql
            if "IF NOT EXISTS" not in create_sql.upper():
                create_sql = create_sql.replace(
                    "CREATE INDEX ", "CREATE INDEX IF NOT EXISTS "
                )
                create_sql = create_sql.replace(
                    "CREATE UNIQUE INDEX ", "CREATE UNIQUE INDEX IF NOT EXISTS "
                )
            conn.execute(text(create_sql))

    conn.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_user_uuid ON users (user_uuid);"
        )
    )

    # 7. Recreate triggers
    for _name, sql in triggers:
        if sql:
            conn.execute(text(sql))

    # 8. Verify relational integrity
    fk_violations = conn.execute(text("PRAGMA foreign_key_check;")).fetchall()
    if fk_violations:
        raise RuntimeError(
            f"Foreign key violations detected after users table rebuild: {fk_violations}"
        )


if __name__ == "__main__":
    run_migration()
