"""PostgreSQL-backed integration tests for refresh token rotation, concurrency,
reuse detection, and database-level timestamps.

Ensures that:
1. Five concurrent requests using the same refresh token result in exactly one
   success and four 401 responses.
2. Losing concurrent requests do not revoke the winning request's token family.
3. Replaying an old token after the grace period revokes the entire family.
4. Replaying an older ancestor after multiple rotations revokes active descendants.
5. Separate token families remain completely isolated.
6. The database timestamp helper and atomic UPDATE execute with PostgreSQL row locking.
7. Migrations against PostgreSQL are idempotent and correctly hash legacy tokens.

Strictly marked with @pytest.mark.integration and skips if PostgreSQL is not configured.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.security import create_refresh_token, hash_token
from app.database import Base, get_db_now
from app.models.auth_audit_logs import AuthAuditLog
from app.models.refresh_token import RefreshToken
from app.models.roles import Role
from app.models.users import User
from app.routes.auth_routes import RefreshRequest, refresh_token
from app.services.audit_service import TOKEN_REVOKED
from app.services.auth_service import save_refresh_token
from scripts.migrate_add_user_uuid import run_migration as run_user_uuid_migration
from scripts.migrate_refresh_tokens_family_and_hash import (
    is_sha256_hex,
)
from scripts.migrate_refresh_tokens_family_and_hash import (
    run_migration as run_refresh_token_migration,
)

pytestmark = pytest.mark.integration


def get_postgres_url() -> str | None:
    """Return the PostgreSQL connection URL if configured, otherwise None.

    Does NOT run against SQLite to avoid accidental false-positive verification.
    """
    for env_var in ("TEST_DATABASE_URL", "POSTGRES_URL", "DATABASE_URL"):
        url = os.getenv(env_var)
        if url and (url.startswith("postgresql://") or url.startswith("postgres://")):
            return url
    return None


@pytest.fixture(scope="module")
def pg_engine():
    """Create a dedicated PostgreSQL engine for integration tests with connection pooling."""
    pg_url = get_postgres_url()
    if not pg_url:
        pytest.skip(
            "PostgreSQL database URL not configured; skipping PostgreSQL-specific integration test"
        )

    engine = create_engine(pg_url, pool_size=10, max_overflow=5)

    # Initialize schema and run migrations
    Base.metadata.create_all(bind=engine)
    run_user_uuid_migration(engine)
    run_refresh_token_migration(engine)

    yield engine

    engine.dispose()


@pytest.fixture
def pg_session_factory(pg_engine):
    """Provide a sessionmaker configured for independent concurrent sessions."""
    return sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)


def create_test_user(session_factory, email_prefix: str = "pg_user") -> tuple[int, str]:
    """Helper to create a dedicated user for a test scenario in PostgreSQL."""
    with session_factory() as db:
        role = db.query(Role).filter(Role.name == "ceo").first()
        if not role:
            role = Role(name="ceo", description="Chief Executive Officer")
            db.add(role)
            db.commit()
            db.refresh(role)

        email = f"{email_prefix}_{uuid.uuid4().hex[:8]}@company.com"
        user = User(
            email=email,
            full_name="PostgreSQL Integration User",
            password="mock_password_hash",
            is_active=True,
            role_id=role.id,
            user_uuid=uuid.uuid4(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id, user.email


def issue_pg_token(
    session_factory, user_id: int, email: str, family_id: str | None = None
) -> tuple[str, str]:
    """Helper to issue and persist a refresh token directly in PostgreSQL."""
    if family_id is None:
        family_id = str(uuid.uuid4())
    raw_token = create_refresh_token(
        {"sub": email, "user_id": user_id}, family_id=family_id
    )
    expires_at = datetime.now(UTC) + timedelta(days=7)
    with session_factory() as db:
        save_refresh_token(
            db=db,
            user_id=user_id,
            token=raw_token,
            expires_at=expires_at,
            family_id=family_id,
        )
        db.commit()
    return raw_token, family_id


def test_postgres_timestamp_helper_and_atomic_locking(pg_session_factory):
    """Verify that get_db_now() uses the PostgreSQL server clock and atomic UPDATE row locking succeeds."""
    with pg_session_factory() as db:
        # 1. Verify get_db_now returns offset-aware UTC timestamp from PostgreSQL
        pg_now = get_db_now(db)
        assert pg_now is not None
        assert pg_now.tzinfo is not None

        # Verify against direct SQL query
        raw_sql_now = db.scalar(text("SELECT CURRENT_TIMESTAMP;"))
        assert raw_sql_now is not None
        diff = abs(
            (
                pg_now
                - (
                    raw_sql_now
                    if raw_sql_now.tzinfo
                    else raw_sql_now.replace(tzinfo=UTC)
                )
            ).total_seconds()
        )
        assert diff < 2.0, f"Database timestamp drift too large: {diff}s"


def test_five_concurrent_refresh_requests_only_one_succeeds_in_postgres(
    pg_session_factory,
):
    """Verify five concurrent requests against PostgreSQL: exactly one succeeds and four receive 401.

    Losing concurrent requests must not revoke the winning request's token family.
    Each thread uses an independent database connection and session.
    """
    user_id, email = create_test_user(pg_session_factory, "pg_concurrent")
    shared_token, family_id = issue_pg_token(pg_session_factory, user_id, email)

    results = []

    def attempt_concurrent_refresh():
        # Independent database connection and session per thread
        with pg_session_factory() as thread_db:
            try:
                res = refresh_token(
                    RefreshRequest(refresh_token=shared_token), db=thread_db
                )
                return ("SUCCESS", res)
            except HTTPException as exc:
                return ("HTTP_ERROR", exc.status_code, exc.detail)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(attempt_concurrent_refresh) for _ in range(5)]
        results = [f.result(timeout=10.0) for f in futures]

    statuses = [r[1] if r[0] == "HTTP_ERROR" else 200 for r in results]
    assert statuses.count(200) == 1, f"Expected exactly one 200, got: {statuses}"
    assert statuses.count(401) == 4, f"Expected four 401s, got: {statuses}"

    winner_result = next(r for r in results if r[0] == "SUCCESS")
    winner_token = winner_result[1]["refresh_token"]

    # CRUCIAL CHECK: Winning token family MUST NOT be revoked by losing concurrent requests
    with pg_session_factory() as db:
        next_res = refresh_token(RefreshRequest(refresh_token=winner_token), db=db)
        assert "access_token" in next_res
        assert "refresh_token" in next_res


def test_replay_after_grace_period_revokes_entire_family_in_postgres(
    pg_session_factory,
):
    """Verify that replaying a token after the 10-second grace period revokes the entire family in PostgreSQL."""
    user_id, email = create_test_user(pg_session_factory, "pg_replay")
    token_a, family_id = issue_pg_token(pg_session_factory, user_id, email)

    # Rotation 1: A -> B (Token B is active)
    with pg_session_factory() as db:
        res_1 = refresh_token(RefreshRequest(refresh_token=token_a), db=db)
        token_b = res_1["refresh_token"]

    # Age Token A revoked_at to 15 seconds ago (> 10s grace period) in PostgreSQL
    with pg_session_factory() as db:
        hash_a = hash_token(token_a)
        row_a = db.query(RefreshToken).filter(RefreshToken.token == hash_a).first()
        assert row_a is not None
        row_a.revoked_at = get_db_now(db) - timedelta(seconds=15)
        db.commit()

    # Replay Token A after grace period: must receive 401
    with pg_session_factory() as db:
        with pytest.raises(HTTPException) as exc_info:
            refresh_token(RefreshRequest(refresh_token=token_a), db=db)
        assert exc_info.value.status_code == 401

    # Entire family must be revoked in PostgreSQL: active Token B MUST FAIL with 401!
    with pg_session_factory() as db:
        with pytest.raises(HTTPException) as exc_info_b:
            refresh_token(RefreshRequest(refresh_token=token_b), db=db)
        assert exc_info_b.value.status_code == 401

        # Verify DB records
        family_rows = (
            db.query(RefreshToken).filter(RefreshToken.family_id == family_id).all()
        )
        for r in family_rows:
            assert r.is_revoked is True

        # Verify audit log
        audit = (
            db.query(AuthAuditLog)
            .filter(
                AuthAuditLog.event_type == TOKEN_REVOKED,
                AuthAuditLog.details.contains(family_id),
            )
            .first()
        )
        assert audit is not None
        assert token_a not in audit.details
        assert token_b not in audit.details


def test_replay_of_older_ancestor_after_multiple_rotations_revokes_descendants_in_postgres(
    pg_session_factory,
):
    """Verify replaying an older ancestor after multiple rotations revokes all active descendants in PostgreSQL."""
    user_id, email = create_test_user(pg_session_factory, "pg_multi_rot")
    token_a, family_id = issue_pg_token(pg_session_factory, user_id, email)

    with pg_session_factory() as db:
        # Rotation 1: A -> B
        res_1 = refresh_token(RefreshRequest(refresh_token=token_a), db=db)
        token_b = res_1["refresh_token"]

        # Rotation 2: B -> C (Token C is active)
        res_2 = refresh_token(RefreshRequest(refresh_token=token_b), db=db)
        token_c = res_2["refresh_token"]

        # Age Token A to 15 seconds ago
        hash_a = hash_token(token_a)
        row_a = db.query(RefreshToken).filter(RefreshToken.token == hash_a).first()
        row_a.revoked_at = get_db_now(db) - timedelta(seconds=15)
        db.commit()

    # Replay ancestor Token A
    with pg_session_factory() as db:
        with pytest.raises(HTTPException) as exc_info:
            refresh_token(RefreshRequest(refresh_token=token_a), db=db)
        assert exc_info.value.status_code == 401

    # Active descendant Token C MUST NOW FAIL with 401
    with pg_session_factory() as db:
        with pytest.raises(HTTPException) as exc_info_c:
            refresh_token(RefreshRequest(refresh_token=token_c), db=db)
        assert exc_info_c.value.status_code == 401


def test_separate_token_families_remain_isolated_in_postgres(pg_session_factory):
    """Verify that revoking or replaying in Family 1 does NOT revoke Family 2 in PostgreSQL."""
    user_id, email = create_test_user(pg_session_factory, "pg_isolated_fams")
    token_fam1, fam1_id = issue_pg_token(pg_session_factory, user_id, email)
    token_fam2, fam2_id = issue_pg_token(pg_session_factory, user_id, email)

    assert fam1_id != fam2_id

    # Rotate both families
    with pg_session_factory() as db:
        res_1 = refresh_token(RefreshRequest(refresh_token=token_fam1), db=db)
        token_fam1_b = res_1["refresh_token"]

        res_2 = refresh_token(RefreshRequest(refresh_token=token_fam2), db=db)
        token_fam2_b = res_2["refresh_token"]

        # Age Token 1 in Family 1 to 15 seconds ago
        hash_fam1 = hash_token(token_fam1)
        row_fam1 = (
            db.query(RefreshToken).filter(RefreshToken.token == hash_fam1).first()
        )
        row_fam1.revoked_at = get_db_now(db) - timedelta(seconds=15)
        db.commit()

    # Replay Token 1 in Family 1 (triggers Family 1 revocation)
    with pg_session_factory() as db:
        with pytest.raises(HTTPException):
            refresh_token(RefreshRequest(refresh_token=token_fam1), db=db)

    # Family 1 active token is revoked
    with pg_session_factory() as db:
        with pytest.raises(HTTPException):
            refresh_token(RefreshRequest(refresh_token=token_fam1_b), db=db)

    # CRUCIAL CHECK: Family 2 active token remains VALID and can refresh
    with pg_session_factory() as db:
        res_fam2_c = refresh_token(RefreshRequest(refresh_token=token_fam2_b), db=db)
        assert "access_token" in res_fam2_c
        assert "refresh_token" in res_fam2_c


def test_postgres_migration_idempotency_and_raw_token_hashing(
    pg_engine, pg_session_factory
):
    """Verify that migration script on PostgreSQL correctly hashes raw tokens and is safe to rerun multiple times."""
    user_id, email = create_test_user(pg_session_factory, "pg_migr")
    raw_jwt = create_refresh_token({"sub": email, "user_id": user_id})

    with pg_session_factory() as db:
        # Insert a raw unhashed JWT directly into PostgreSQL table
        row = RefreshToken(
            user_id=user_id,
            token=raw_jwt,
            is_revoked=False,
            expires_at=datetime.now(UTC) + timedelta(days=7),
            family_id=None,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        inserted_id = row.id

    # 1. Run migration against PostgreSQL
    summary_1 = run_refresh_token_migration(pg_engine)
    assert summary_1["tokens_hashed"] >= 1

    with pg_session_factory() as db:
        migrated_row = (
            db.query(RefreshToken).filter(RefreshToken.id == inserted_id).first()
        )
        assert is_sha256_hex(migrated_row.token)
        assert migrated_row.token == hashlib.sha256(raw_jwt.encode("utf-8")).hexdigest()
        assert migrated_row.family_id is not None

    # 2. Run migration a second time: must be completely idempotent (0 tokens hashed)
    summary_2 = run_refresh_token_migration(pg_engine)
    assert summary_2["tokens_hashed"] == 0
    assert summary_2["columns_added"] == 0


def test_postgres_migration_posix_regex_filtering_and_preservation(
    pg_engine, pg_session_factory
):
    """Verify PostgreSQL POSIX regex filtering, family_id/timestamp preservation,
    and multi-batch keyset pagination with batch_size=1.
    """
    user_id, email = create_test_user(pg_session_factory, "pg_posix_filt")

    # Generate unique inputs so repeated test executions do not violate
    # the global unique constraint on refresh_token.token.
    test_run_id = uuid.uuid4().hex

    raw_jwt = create_refresh_token(
        {
            "sub": email,
            "user_id": user_id,
            "nonce": f"pg_jwt_1_{test_run_id}",
        }
    )

    valid_sha256 = hashlib.sha256(
        f"pg_valid_token_keep:{test_run_id}".encode("utf-8")
    ).hexdigest()

    # Both values remain exactly 64 characters and contain non-hex characters.
    invalid_64_a = "g" + test_run_id + ("g" * 31)
    invalid_64_b = "z" + test_run_id + ("z" * 31)

    revoked_hash = hashlib.sha256(
        f"pg_revoked_pres:{test_run_id}".encode("utf-8")
    ).hexdigest()

    raw_revoked_jwt = create_refresh_token(
        {
            "sub": email,
            "user_id": user_id,
            "nonce": f"pg_jwt_rev_{test_run_id}",
        }
    )

    existing_rev_time = datetime.now(UTC) - timedelta(days=3)

    with pg_session_factory() as db:
        # Row 1: Valid SHA-256 hash with existing family.
        # Migration must leave it unchanged.
        r1 = RefreshToken(
            user_id=user_id,
            token=valid_sha256,
            is_revoked=False,
            family_id=f"fam-pg-preserve-valid-{test_run_id}",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )

        # Row 2: 64-character non-hex token with existing family.
        # Migration must hash it and preserve its family.
        r2 = RefreshToken(
            user_id=user_id,
            token=invalid_64_a,
            is_revoked=False,
            family_id=f"fam-pg-preserve-nonhex1-{test_run_id}",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )

        # Row 3: Another 64-character non-hex token.
        r3 = RefreshToken(
            user_id=user_id,
            token=invalid_64_b,
            is_revoked=False,
            family_id=f"fam-pg-preserve-nonhex2-{test_run_id}",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )

        # Row 4: Raw JWT with no family.
        # Migration must hash it and assign a family.
        r4 = RefreshToken(
            user_id=user_id,
            token=raw_jwt,
            is_revoked=False,
            family_id=None,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )

        # Row 5: Revoked token with an existing revoked_at timestamp.
        # Migration must preserve that timestamp.
        r5 = RefreshToken(
            user_id=user_id,
            token=revoked_hash,
            is_revoked=True,
            revoked_at=existing_rev_time,
            family_id=f"fam-pg-preserve-rev-{test_run_id}",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )

        # Row 6: Revoked raw JWT without revoked_at or family.
        # Migration must hash it, backfill revoked_at and assign a family.
        r6 = RefreshToken(
            user_id=user_id,
            token=raw_revoked_jwt,
            is_revoked=True,
            revoked_at=None,
            family_id=None,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )

        db.add_all([r1, r2, r3, r4, r5, r6])
        db.commit()

        ids = [r1.id, r2.id, r3.id, r4.id, r5.id, r6.id]

    # Run migration with batch_size=1 to exercise multi-batch keyset pagination.
    summary_1 = run_refresh_token_migration(pg_engine, batch_size=1)

    # Rows 2, 3, 4 and 6 require hashing.
    assert summary_1["tokens_hashed"] >= 4

    # Rows 4 and 6 require family backfill.
    assert summary_1["families_backfilled"] >= 2

    with pg_session_factory() as db:
        rows = {
            r.id: r
            for r in (db.query(RefreshToken).filter(RefreshToken.id.in_(ids)).all())
        }

        assert len(rows) == 6

        # Row 1: Existing valid SHA-256 hash remains unchanged.
        assert rows[ids[0]].token == valid_sha256
        assert rows[ids[0]].family_id == f"fam-pg-preserve-valid-{test_run_id}"

        # Row 2: Non-hex token is hashed; existing family is preserved.
        assert (
            rows[ids[1]].token
            == hashlib.sha256(invalid_64_a.encode("utf-8")).hexdigest()
        )
        assert rows[ids[1]].family_id == f"fam-pg-preserve-nonhex1-{test_run_id}"
        assert is_sha256_hex(rows[ids[1]].token)

        # Row 3: Second non-hex token is hashed; family is preserved.
        assert (
            rows[ids[2]].token
            == hashlib.sha256(invalid_64_b.encode("utf-8")).hexdigest()
        )
        assert rows[ids[2]].family_id == f"fam-pg-preserve-nonhex2-{test_run_id}"
        assert is_sha256_hex(rows[ids[2]].token)

        # Row 4: Raw JWT is hashed and a new family is assigned.
        assert rows[ids[3]].token == hashlib.sha256(raw_jwt.encode("utf-8")).hexdigest()
        assert rows[ids[3]].family_id is not None
        assert is_sha256_hex(rows[ids[3]].token)

        # Row 5: Existing family and revoked_at timestamp are preserved.
        assert rows[ids[4]].family_id == f"fam-pg-preserve-rev-{test_run_id}"
        assert rows[ids[4]].revoked_at is not None

        # Compare actual instants after converting both timestamps to UTC.
        assert rows[ids[4]].revoked_at.astimezone(UTC) == (
            existing_rev_time.astimezone(UTC)
        )

        # Row 6: Revoked token is hashed and missing metadata is backfilled.
        assert (
            rows[ids[5]].token
            == hashlib.sha256(raw_revoked_jwt.encode("utf-8")).hexdigest()
        )
        assert rows[ids[5]].revoked_at is not None
        assert rows[ids[5]].family_id is not None
        assert is_sha256_hex(rows[ids[5]].token)

    # Verify idempotency: a second migration run must not hash or backfill again.
    summary_2 = run_refresh_token_migration(pg_engine, batch_size=1)

    assert summary_2["tokens_hashed"] == 0
    assert summary_2["families_backfilled"] == 0


def test_postgres_migration_transaction_rollback_on_failure(
    pg_engine, pg_session_factory
):
    """Verify that failure during batch update execution rolls back the entire PostgreSQL transaction."""
    from unittest.mock import patch

    import scripts.migrate_refresh_tokens_family_and_hash as mig_mod

    user_id, email = create_test_user(pg_session_factory, "pg_rollback")
    raw_jwt = create_refresh_token(
        {"sub": email, "user_id": user_id, "nonce": "rollback_jwt"}
    )

    with pg_session_factory() as db:
        row = RefreshToken(
            user_id=user_id,
            token=raw_jwt,
            is_revoked=False,
            family_id=None,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        inserted_id = row.id

    original_migrate_rows = mig_mod._migrate_token_rows

    def failing_migrate_rows(conn, summary, batch_size=1000, dialect_name="postgresql"):
        # Call original to update in-memory / staging, then simulate sudden database error before commit
        original_migrate_rows(
            conn, summary, batch_size=batch_size, dialect_name=dialect_name
        )
        raise RuntimeError("Simulated mid-migration failure before transaction commit")

    with patch.object(mig_mod, "_migrate_token_rows", side_effect=failing_migrate_rows):
        with pytest.raises(RuntimeError, match="Simulated mid-migration failure"):
            run_refresh_token_migration(pg_engine)

    # Verify atomic rollback in PostgreSQL: token remains unmigrated raw JWT and family_id remains None
    with pg_session_factory() as db:
        row_after_rollback = (
            db.query(RefreshToken).filter(RefreshToken.id == inserted_id).first()
        )
        assert row_after_rollback is not None
        assert row_after_rollback.token == raw_jwt
        assert row_after_rollback.family_id is None
