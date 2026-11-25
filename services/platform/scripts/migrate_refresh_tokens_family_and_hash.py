"""Safe, idempotent migration to add family_id and revoked_at to refresh_token,
and hash existing raw refresh tokens to SHA-256.

Supports PostgreSQL and SQLite.
Safe to rerun multiple times.

Usage:
    python scripts/migrate_refresh_tokens_family_and_hash.py
"""

from __future__ import annotations

import hashlib
import sys
import uuid
from datetime import UTC, datetime
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


def is_sha256_hex(val: str) -> bool:
    """Check if value is already a 64-character SHA-256 hex string."""
    if not val or len(val) != 64 or "." in val:
        return False
    try:
        int(val, 16)
        return True
    except ValueError:
        return False


def hash_token(token: str) -> str:
    """Hash token with SHA-256 if not already a 64-char sha256 hex digest."""
    if is_sha256_hex(token):
        return token
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def run_migration(engine: Engine | None = None) -> dict[str, int]:
    """Execute the refresh token family and SHA-256 hashing migration against the given engine.

    Returns a summary dict with counts of columns added, tokens hashed,
    and families backfilled.
    """
    if engine is None:
        engine = default_engine

    dialect_name = engine.dialect.name
    if dialect_name not in ("sqlite", "postgresql"):
        raise RuntimeError(
            f"Unsupported database dialect: '{dialect_name}'. Only 'sqlite' and 'postgresql' are supported."
        )

    summary = {
        "columns_added": 0,
        "tokens_hashed": 0,
        "families_backfilled": 0,
        "index_created": 0,
    }

    inspector = sa.inspect(engine)
    if not inspector.has_table("refresh_token"):
        return summary

    columns = [col["name"] for col in inspector.get_columns("refresh_token")]

    if dialect_name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text("LOCK TABLE refresh_token IN SHARE ROW EXCLUSIVE MODE;"))
            tx_inspector = sa.inspect(conn)
            tx_columns = {
                col["name"]: col for col in tx_inspector.get_columns("refresh_token")
            }

            # 1. Add family_id if not present
            if "family_id" not in tx_columns:
                conn.execute(
                    text("ALTER TABLE refresh_token ADD COLUMN family_id VARCHAR(64);")
                )
                summary["columns_added"] += 1

            # 2. Add revoked_at if not present
            if "revoked_at" not in tx_columns:
                conn.execute(
                    text(
                        "ALTER TABLE refresh_token ADD COLUMN revoked_at TIMESTAMP WITH TIME ZONE;"
                    )
                )
                summary["columns_added"] += 1

            # 3. Create index on family_id if not present
            tx_indexes = [
                idx["name"] for idx in tx_inspector.get_indexes("refresh_token")
            ]
            if "ix_refresh_token_family_id" not in tx_indexes:
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_refresh_token_family_id ON refresh_token (family_id);"
                    )
                )
                summary["index_created"] += 1

            # 4. Migrate existing rows: backfill family_id and hash raw tokens
            rows = conn.execute(
                text(
                    "SELECT id, token, family_id, is_revoked, revoked_at, created_at FROM refresh_token;"
                )
            ).fetchall()

            for row_id, raw_token, fam_id, is_rev, rev_at, cr_at in rows:
                needs_update = False
                new_token = raw_token
                new_fam = fam_id
                new_rev_at = rev_at

                if not fam_id:
                    new_fam = str(uuid.uuid4())
                    needs_update = True
                    summary["families_backfilled"] += 1

                if not is_sha256_hex(raw_token):
                    new_token = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
                    needs_update = True
                    summary["tokens_hashed"] += 1

                if is_rev and rev_at is None:
                    new_rev_at = cr_at or datetime.now(UTC)
                    needs_update = True

                if needs_update:
                    conn.execute(
                        text(
                            "UPDATE refresh_token "
                            "SET token = :token, family_id = :family_id, revoked_at = :revoked_at "
                            "WHERE id = :row_id;"
                        ),
                        {
                            "token": new_token,
                            "family_id": new_fam,
                            "revoked_at": new_rev_at,
                            "row_id": row_id,
                        },
                    )

    elif dialect_name == "sqlite":
        with engine.begin() as conn:
            # 1. Add family_id if not present
            if "family_id" not in columns:
                conn.execute(
                    text("ALTER TABLE refresh_token ADD COLUMN family_id VARCHAR(64);")
                )
                summary["columns_added"] += 1

            # 2. Add revoked_at if not present
            if "revoked_at" not in columns:
                conn.execute(
                    text("ALTER TABLE refresh_token ADD COLUMN revoked_at DATETIME;")
                )
                summary["columns_added"] += 1

            # 3. Create index on family_id if not present
            indexes = [idx["name"] for idx in inspector.get_indexes("refresh_token")]
            if "ix_refresh_token_family_id" not in indexes:
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_refresh_token_family_id ON refresh_token (family_id);"
                    )
                )
                summary["index_created"] += 1

            # 4. Migrate existing rows
            rows = conn.execute(
                text(
                    "SELECT id, token, family_id, is_revoked, revoked_at, created_at FROM refresh_token;"
                )
            ).fetchall()

            for row_id, raw_token, fam_id, is_rev, rev_at, cr_at in rows:
                needs_update = False
                new_token = raw_token
                new_fam = fam_id
                new_rev_at = rev_at

                if not fam_id:
                    new_fam = str(uuid.uuid4())
                    needs_update = True
                    summary["families_backfilled"] += 1

                if not is_sha256_hex(raw_token):
                    new_token = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
                    needs_update = True
                    summary["tokens_hashed"] += 1

                if is_rev and rev_at is None:
                    new_rev_at = cr_at or datetime.now(UTC)
                    needs_update = True

                if needs_update:
                    conn.execute(
                        text(
                            "UPDATE refresh_token "
                            "SET token = :token, family_id = :family_id, revoked_at = :revoked_at "
                            "WHERE id = :row_id;"
                        ),
                        {
                            "token": new_token,
                            "family_id": new_fam,
                            "revoked_at": new_rev_at,
                            "row_id": row_id,
                        },
                    )

    return summary


if __name__ == "__main__":
    result = run_migration()
    print(f"Migration completed: {result}")
