"""Tests for UUID User ID in tokens and /verify (Round 15 Issue #259 - R15-RH5).

Covers:
1. User model UUID generation, uniqueness, and SQLite/PostgreSQL compatibility.
2. Migration script (migrate_add_user_uuid.py) column addition, backfill, and idempotency.
3. JWT access token claim generation across login, MFA, refresh, and SSO.
4. /api/v1/auth/verify endpoint responses, caching, and token validation.
5. Deterministic demo user UUIDs and seed idempotency.
6. Platform /verify contract specification and consumer compatibility.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from starlette.testclient import TestClient

from app.core.security import create_access_token, decode_token
from app.database import Base, SessionLocal
from app.main import app
from app.models.roles import Role
from app.models.users import User
from app.schemas.auth import VerifyResponse
from app.seed import DEMO_USER_UUIDS, seed_database
from scripts.migrate_add_user_uuid import run_migration

# ============================================================================
# 1. MODEL & DATABASE TESTS
# ============================================================================


def test_user_model_auto_generates_uuid():
    """A newly created user without an explicit UUID receives a valid UUID v4 upon insert."""
    db: Session = SessionLocal()
    try:
        email = f"auto-uuid-{uuid.uuid4().hex[:8]}@example.com"
        user = User(
            email=email,
            full_name="Auto UUID User",
            password="hashed-password-123",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        assert user.id is not None
        assert isinstance(user.id, int)
        assert user.user_uuid is not None
        assert isinstance(user.user_uuid, uuid.UUID)
        assert user.user_uuid.version == 4
    finally:
        db.rollback()
        db.close()


def test_user_model_preserves_explicit_uuid():
    """An explicitly provided UUID is persisted without modification."""
    db: Session = SessionLocal()
    try:
        custom_uuid = uuid.UUID("11111111-2222-4333-8444-555555555555")
        email = f"explicit-uuid-{uuid.uuid4().hex[:8]}@example.com"
        user = User(
            email=email,
            user_uuid=custom_uuid,
            full_name="Explicit UUID User",
            password="hashed-password-123",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        assert user.user_uuid == custom_uuid
    finally:
        db.rollback()
        db.close()


def test_user_model_uuid_uniqueness():
    """Two different users cannot share the same user_uuid."""
    db: Session = SessionLocal()
    try:
        shared_uuid = uuid.UUID("22222222-3333-4444-8555-666666666666")
        u1 = User(
            email=f"u1-{uuid.uuid4().hex[:8]}@example.com",
            user_uuid=shared_uuid,
            full_name="User One",
            password="pwd",
            is_active=True,
        )
        db.add(u1)
        db.commit()

        u2 = User(
            email=f"u2-{uuid.uuid4().hex[:8]}@example.com",
            user_uuid=shared_uuid,
            full_name="User Two",
            password="pwd",
            is_active=True,
        )
        db.add(u2)
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_user_model_foreign_key_and_integer_id():
    """Existing integer id and foreign-key relationships continue working seamlessly."""
    db: Session = SessionLocal()
    try:
        role = db.query(Role).filter(Role.name == "analyst").first()
        assert role is not None

        email = f"fk-test-{uuid.uuid4().hex[:8]}@example.com"
        user = User(
            email=email,
            full_name="FK Test User",
            password="pwd",
            role_id=role.id,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        assert isinstance(user.id, int)
        assert user.role_id == role.id
        assert user.role is not None
        assert user.role.name == "analyst"
        assert isinstance(user.user_uuid, uuid.UUID)
    finally:
        db.rollback()
        db.close()


# ============================================================================
# 2. MIGRATION TESTS
# ============================================================================


def test_migration_adds_column_and_backfills_users():
    """Migration adds user_uuid column, backfills demo and custom users, and creates index."""
    test_engine = create_engine("sqlite:///:memory:")

    with test_engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE users ("
                "id INTEGER PRIMARY KEY, "
                "email VARCHAR(255) NOT NULL, "
                "full_name VARCHAR(255) NOT NULL"
                ");"
            )
        )
        conn.execute(
            text(
                "INSERT INTO users (id, email, full_name) VALUES "
                "(1, 'ceo@company.com', 'Demo CEO'), "
                "(2, 'warehousemanager@company.com', 'Demo Warehouse'), "
                "(3, 'custom.user@example.com', 'Custom User');"
            )
        )

    summary = run_migration(test_engine)
    assert summary["column_added"] == 1
    assert summary["users_backfilled"] == 3
    assert summary["index_created"] == 1

    with test_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, email, user_uuid FROM users ORDER BY id;")
        ).fetchall()

        assert len(rows) == 3
        # Demo users received their fixed UUIDs
        assert rows[0][2] == DEMO_USER_UUIDS["ceo@company.com"].hex
        assert rows[1][2] == DEMO_USER_UUIDS["warehousemanager@company.com"].hex
        # Custom user received a unique, valid UUID
        assert rows[2][2] is not None
        assert len(rows[2][2]) == 32
        custom_parsed = uuid.UUID(hex=rows[2][2])
        assert custom_parsed != DEMO_USER_UUIDS["ceo@company.com"]


def test_migration_is_idempotent():
    """Re-running migration on an already-migrated database is safe and does not alter data."""
    test_engine = create_engine("sqlite:///:memory:")

    with test_engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE users ("
                "id INTEGER PRIMARY KEY, "
                "email VARCHAR(255) NOT NULL, "
                "full_name VARCHAR(255) NOT NULL"
                ");"
            )
        )
        conn.execute(
            text(
                "INSERT INTO users (id, email, full_name) VALUES "
                "(1, 'ceo@company.com', 'Demo CEO');"
            )
        )

    run1 = run_migration(test_engine)
    assert run1["column_added"] == 1
    assert run1["users_backfilled"] == 1

    with test_engine.connect() as conn:
        initial_uuid = conn.execute(
            text("SELECT user_uuid FROM users WHERE id = 1;")
        ).scalar()

    run2 = run_migration(test_engine)
    assert run2["column_added"] == 0
    assert run2["users_backfilled"] == 0
    assert run2["index_created"] == 0

    with test_engine.connect() as conn:
        after_uuid = conn.execute(
            text("SELECT user_uuid FROM users WHERE id = 1;")
        ).scalar()

    assert initial_uuid == after_uuid


def test_migration_empty_table():
    """Migration runs cleanly on an empty users table and is idempotent."""
    test_engine = create_engine("sqlite:///:memory:")

    with test_engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE users ("
                "id INTEGER PRIMARY KEY, "
                "email VARCHAR(255) NOT NULL, "
                "full_name VARCHAR(255) NOT NULL"
                ");"
            )
        )

    # First run: adds column, backfills 0 rows, creates index, enforces NOT NULL
    summary1 = run_migration(test_engine)
    assert summary1["column_added"] == 1
    assert summary1["users_backfilled"] == 0
    assert summary1["index_created"] == 1

    # Verify column NOT NULL constraint enforced on SQLite
    with test_engine.connect() as conn:
        col_info = conn.execute(text("PRAGMA table_info(users);")).fetchall()
        user_uuid_col = next(col for col in col_info if col[1] == "user_uuid")
        assert user_uuid_col[3] == 1, "user_uuid must have notnull == 1"

        # Direct INSERT of NULL user_uuid must fail database-level constraint
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO users (id, email, full_name, user_uuid) "
                    "VALUES (1, 'empty@example.com', 'Empty User', NULL);"
                )
            )

    # Second run: fully idempotent
    summary2 = run_migration(test_engine)
    assert summary2["column_added"] == 0
    assert summary2["users_backfilled"] == 0
    assert summary2["index_created"] == 0


def test_migration_partially_migrated_database():
    """Partially migrated table preserves existing UUIDs, backfills NULLs, enforces NOT NULL,

    preserves existing data, and remains idempotent on re-run.
    """
    test_engine = create_engine("sqlite:///:memory:")

    existing_uuid_hex = "11111111222233334444555566667777"

    with test_engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE users ("
                "id INTEGER PRIMARY KEY, "
                "email VARCHAR(255) NOT NULL, "
                "full_name VARCHAR(255) NOT NULL, "
                "user_uuid CHAR(32)"
                ");"
            )
        )
        conn.execute(
            text(
                "INSERT INTO users (id, email, full_name, user_uuid) VALUES "
                f"(1, 'already.has.uuid@example.com', 'Existing UUID User', '{existing_uuid_hex}'), "
                "(2, 'needs.uuid@example.com', 'Missing UUID User', NULL);"
            )
        )

    # First migration run
    summary1 = run_migration(test_engine)
    assert summary1["column_added"] == 0
    assert summary1["users_backfilled"] == 1
    assert summary1["index_created"] == 1

    with test_engine.connect() as conn:
        # Verify resulting column is NOT NULL
        col_info = conn.execute(text("PRAGMA table_info(users);")).fetchall()
        user_uuid_col = next(col for col in col_info if col[1] == "user_uuid")
        assert user_uuid_col[3] == 1, "user_uuid column must have notnull == 1"

        # Direct INSERT of NULL user_uuid must fail database-level NOT NULL constraint
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO users (id, email, full_name, user_uuid) "
                    "VALUES (3, 'another@example.com', 'Null User', NULL);"
                )
            )

        # Verify existing user IDs and data remain unchanged, existing UUID preserved, missing backfilled
        rows = conn.execute(
            text("SELECT id, email, full_name, user_uuid FROM users ORDER BY id;")
        ).fetchall()
        assert len(rows) == 2

        # User 1: existing UUID preserved verbatim
        assert rows[0][0] == 1
        assert rows[0][1] == "already.has.uuid@example.com"
        assert rows[0][2] == "Existing UUID User"
        assert rows[0][3] == existing_uuid_hex

        # User 2: missing UUID backfilled
        assert rows[1][0] == 2
        assert rows[1][1] == "needs.uuid@example.com"
        assert rows[1][2] == "Missing UUID User"
        assert rows[1][3] is not None
        assert len(rows[1][3]) == 32
        assert rows[1][3] != existing_uuid_hex
        user2_backfilled_uuid = rows[1][3]

    # Second migration run: succeeds without changing UUIDs
    summary2 = run_migration(test_engine)
    assert summary2["column_added"] == 0
    assert summary2["users_backfilled"] == 0
    assert summary2["index_created"] == 0

    with test_engine.connect() as conn:
        rows_rerun = conn.execute(
            text("SELECT id, email, full_name, user_uuid FROM users ORDER BY id;")
        ).fetchall()
        assert len(rows_rerun) == 2
        assert rows_rerun[0][3] == existing_uuid_hex
        assert rows_rerun[1][3] == user2_backfilled_uuid


def test_migration_rejects_unsupported_dialect():
    """Migration raises RuntimeError if the database engine dialect is not sqlite or postgresql."""

    class UnsupportedEngine:
        class dialect:
            name = "mysql"

    with pytest.raises(RuntimeError, match="Unsupported database dialect: 'mysql'"):
        run_migration(UnsupportedEngine())  # type: ignore[arg-type]


def test_sqlite_migration_enforces_not_null_and_preserves_fk_and_data():
    """SQLite rebuild enforces NOT NULL, preserves existing data, UUIDs, foreign keys and indexes."""
    test_engine = create_engine("sqlite:///:memory:")

    with test_engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON;"))
        conn.execute(
            text(
                "CREATE TABLE roles ("
                "id INTEGER PRIMARY KEY, "
                "name VARCHAR(50) NOT NULL UNIQUE"
                ");"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE users ("
                "id INTEGER PRIMARY KEY, "
                "email VARCHAR(255) NOT NULL UNIQUE, "
                "full_name VARCHAR(255) NOT NULL, "
                "password VARCHAR(255) NOT NULL, "
                "is_active BOOLEAN NOT NULL DEFAULT 1, "
                "role_id INTEGER REFERENCES roles(id), "
                "supplier_id VARCHAR(100)"
                ");"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE auth_audit_logs ("
                "id INTEGER PRIMARY KEY, "
                "user_id INTEGER REFERENCES users(id), "
                "action VARCHAR(50) NOT NULL"
                ");"
            )
        )
        conn.execute(text("CREATE UNIQUE INDEX ix_users_email ON users(email);"))
        conn.execute(text("CREATE INDEX ix_users_supplier_id ON users(supplier_id);"))
        conn.execute(text("INSERT INTO roles (id, name) VALUES (1, 'admin');"))
        conn.execute(
            text(
                "INSERT INTO users (id, email, full_name, password, is_active, role_id, supplier_id) "
                "VALUES (10, 'ceo@company.com', 'Demo CEO', 'pwd-hash', 1, 1, NULL), "
                "(20, 'supplier@company.com', 'Supplier Rep', 'pwd-hash-2', 1, 1, 'SUP-001');"
            )
        )
        conn.execute(
            text(
                "INSERT INTO auth_audit_logs (id, user_id, action) "
                "VALUES (100, 10, 'LOGIN');"
            )
        )
        conn.commit()

    summary = run_migration(test_engine)
    assert summary["column_added"] == 1
    assert summary["users_backfilled"] == 2
    assert summary["index_created"] == 1

    with test_engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON;"))

        # Verify notnull == 1
        col_info = conn.execute(text("PRAGMA table_info(users);")).fetchall()
        user_uuid_col = next(col for col in col_info if col[1] == "user_uuid")
        assert user_uuid_col[3] == 1

        # Verify existing data preserved
        users = conn.execute(
            text(
                "SELECT id, email, user_uuid, role_id, supplier_id "
                "FROM users ORDER BY id;"
            )
        ).fetchall()
        assert len(users) == 2
        assert users[0][0] == 10
        assert users[0][1] == "ceo@company.com"
        assert users[0][2] == DEMO_USER_UUIDS["ceo@company.com"].hex
        assert users[0][3] == 1
        assert users[0][4] is None

        assert users[1][0] == 20
        assert users[1][1] == "supplier@company.com"
        assert users[1][4] == "SUP-001"

        # Verify child table relation preserved
        audit_logs = conn.execute(
            text("SELECT id, user_id, action FROM auth_audit_logs;")
        ).fetchall()
        assert audit_logs == [(100, 10, "LOGIN")]

        # Verify foreign keys are intact
        violations = conn.execute(text("PRAGMA foreign_key_check;")).fetchall()
        assert violations == []

        # Verify indexes are intact
        index_names = [
            row[0]
            for row in conn.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE tbl_name='users' AND type='index';"
                )
            ).fetchall()
        ]
        assert "ix_users_email" in index_names
        assert "ix_users_supplier_id" in index_names
        assert "ix_users_user_uuid" in index_names

        # Verify NULL user_uuid rejected by constraint
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO users (id, email, full_name, password, is_active, user_uuid) "
                    "VALUES (30, 'other@company.com', 'Other', 'pwd', 1, NULL);"
                )
            )


def test_sqlite_migration_preserves_full_schema_features():
    """SQLite table rebuild preserves collations, CHECK constraints, AUTOINCREMENT,

    triggers, generated columns, and table-level constraints.
    """
    test_engine = create_engine("sqlite:///:memory:")

    with test_engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE users ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "email VARCHAR(255) NOT NULL COLLATE NOCASE, "
                "full_name VARCHAR(255) NOT NULL, "
                "status TEXT DEFAULT 'pending' CHECK (status IN ('active', 'pending')), "
                "gen_name TEXT GENERATED ALWAYS AS (email || ' - ' || full_name) STORED, "
                "CONSTRAINT chk_fn CHECK (length(full_name) > 0)"
                ");"
            )
        )
        conn.execute(
            text(
                "CREATE TRIGGER tr_users_audit AFTER INSERT ON users "
                "BEGIN SELECT 1; END;"
            )
        )
        conn.execute(text("CREATE INDEX ix_users_status ON users(status);"))
        conn.execute(
            text(
                "INSERT INTO users (email, full_name, status) "
                "VALUES ('test@example.com', 'Test User', 'active');"
            )
        )
        conn.commit()

    # Run migration
    summary = run_migration(test_engine)
    assert summary["column_added"] == 1
    assert summary["users_backfilled"] == 1
    assert summary["index_created"] == 1

    with test_engine.connect() as conn:
        final_ddl = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type='table' AND name='users';")
        ).scalar()
        assert final_ddl is not None

        # Verify preservation of full schema features in rebuilt table DDL
        assert "COLLATE NOCASE" in final_ddl
        assert "AUTOINCREMENT" in final_ddl
        assert "CHECK" in final_ddl
        assert "GENERATED ALWAYS AS" in final_ddl
        assert "chk_fn" in final_ddl
        assert "user_uuid" in final_ddl
        assert "NOT NULL" in final_ddl

        # Verify triggers preserved
        triggers = conn.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type='trigger' AND tbl_name='users';"
            )
        ).fetchall()
        assert len(triggers) == 1
        assert triggers[0][0] == "tr_users_audit"

        # Verify indexes preserved
        indexes = [
            row[0]
            for row in conn.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='index' AND tbl_name='users';"
                )
            ).fetchall()
        ]
        assert "ix_users_status" in indexes
        assert "ix_users_user_uuid" in indexes

        # Verify data and generated column computation preserved
        row = conn.execute(
            text("SELECT id, email, full_name, status, gen_name, user_uuid FROM users;")
        ).fetchone()
        assert row is not None
        assert row[0] == 1
        assert row[1] == "test@example.com"
        assert row[2] == "Test User"
        assert row[3] == "active"
        assert row[4] == "test@example.com - Test User"
        assert row[5] is not None
        assert len(row[5]) == 32

        # Verify CHECK constraint is still active
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO users (email, full_name, status, user_uuid) "
                    "VALUES ('invalid@example.com', 'Invalid', 'banned', "
                    "'00112233445566778899aabbccddeeff');"
                )
            )


def test_sqlite_migration_simulated_failure_rolls_back_safely(monkeypatch):
    """A failure during SQLite table rebuild rolls back cleanly without data loss or lingering new tables."""
    from scripts import migrate_add_user_uuid

    test_engine = create_engine("sqlite:///:memory:")

    with test_engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE users ("
                "id INTEGER PRIMARY KEY, "
                "email VARCHAR(255) NOT NULL, "
                "full_name VARCHAR(255) NOT NULL"
                ");"
            )
        )
        conn.execute(
            text(
                "INSERT INTO users (id, email, full_name) VALUES "
                "(1, 'preserve@example.com', 'Preserve User');"
            )
        )
        conn.commit()

    # Simulate an error during _rebuild_sqlite_users_table after adding column
    def failing_rebuild(conn):
        conn.execute(text("CREATE TABLE users_migration_new (id INT);"))
        raise RuntimeError("Simulated failure during table rebuild")

    monkeypatch.setattr(
        migrate_add_user_uuid, "_rebuild_sqlite_users_table", failing_rebuild
    )

    with pytest.raises(RuntimeError, match="Simulated failure during table rebuild"):
        migrate_add_user_uuid.run_migration(test_engine)

    # Verify rollback: original users table and data remain intact, temporary table does not exist
    with test_engine.connect() as conn:
        tables = [
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table';")
            ).fetchall()
        ]
        assert "users" in tables
        assert "users_migration_new" not in tables

        rows = conn.execute(text("SELECT id, email, full_name FROM users;")).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 1
        assert rows[0][1] == "preserve@example.com"


# ============================================================================
# 3. JWT ACCESS TOKEN CLAIMS TESTS
# ============================================================================


def test_jwt_access_token_claims_structure():
    """Access tokens contain user_uuid alongside preserved sub, user_id, and role claims."""
    test_uuid = uuid.uuid4()
    token = create_access_token(
        {
            "sub": "user@example.com",
            "user_id": 42,
            "role": "analyst",
            "user_uuid": str(test_uuid),
        }
    )

    payload = decode_token(token)
    assert payload["sub"] == "user@example.com"
    assert payload["user_id"] == 42
    assert payload["role"] == "analyst"
    assert payload["user_uuid"] == str(test_uuid)
    assert payload["type"] == "access"


def test_login_and_refresh_token_generation_include_user_uuid():
    """Authentication login and refresh endpoints issue access tokens containing user_uuid."""
    client = TestClient(app)
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "ceo@company.com").first()
        assert user is not None
        assert user.user_uuid == DEMO_USER_UUIDS["ceo@company.com"]
        expected_user_id = user.id
    finally:
        db.close()

    # Call /api/v1/auth/login
    from app.seed import _required_password

    password = _required_password("CEO_PASSWORD")
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "ceo@company.com", "password": password},
    )
    assert response.status_code == 200, response.text
    tokens = response.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    # Verify login access token claims
    login_claims = decode_token(tokens["access_token"])
    assert login_claims["sub"] == "ceo@company.com"
    assert login_claims["user_id"] == expected_user_id
    assert login_claims["user_uuid"] == str(DEMO_USER_UUIDS["ceo@company.com"])

    # Call /api/v1/auth/refresh
    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 200, refresh_response.text
    refreshed_tokens = refresh_response.json()

    # Verify refreshed access token claims
    refreshed_claims = decode_token(refreshed_tokens["access_token"])
    assert refreshed_claims["sub"] == "ceo@company.com"
    assert refreshed_claims["user_id"] == expected_user_id
    assert refreshed_claims["user_uuid"] == str(DEMO_USER_UUIDS["ceo@company.com"])


def test_mfa_token_generation_includes_user_uuid(monkeypatch):
    """MFA verification flow issues access tokens containing user_uuid."""
    from app.core import config as app_config
    from app.seed import _required_password

    monkeypatch.setattr(app_config, "MFA_ENABLED", True)
    monkeypatch.setattr(app_config, "MFA_MOCK_OTP", "246810")

    client = TestClient(app)
    password = _required_password("ANALYST_PASSWORD")
    r = client.post(
        "/api/v1/auth/login",
        data={"username": "analyst@company.com", "password": password},
    )
    assert r.status_code == 200
    assert r.json()["mfa_required"] is True
    challenge = r.json()["challenge_id"]

    verify_resp = client.post(
        "/api/v1/auth/mfa/verify",
        json={"challenge_id": challenge, "otp": "246810"},
    )
    assert verify_resp.status_code == 200
    tokens = verify_resp.json()
    assert "access_token" in tokens

    claims = decode_token(tokens["access_token"])
    assert claims["sub"] == "analyst@company.com"
    assert claims["user_uuid"] == str(DEMO_USER_UUIDS["analyst@company.com"])
    assert claims["role"] == "analyst"


def test_sso_token_generation_includes_user_uuid(monkeypatch):
    """SSO authentication flow issues access tokens containing user_uuid."""
    from app.core import config as app_config
    from app.services.sso_service import create_mock_sso_assertion

    monkeypatch.setattr(app_config, "MOCK_SSO_ENABLED", True)
    monkeypatch.setattr(
        app_config,
        "MOCK_SSO_SECRET",
        "test-sso-secret-0123456789abcdef-xyz",
    )

    client = TestClient(app)
    # enterprise-002 maps to vpoperations@company.com
    r = client.post(
        "/api/v1/auth/sso/login",
        json={
            "provider": "mock-enterprise-sso",
            "assertion": create_mock_sso_assertion("enterprise-002"),
        },
    )
    assert r.status_code == 200
    tokens = r.json()
    assert "access_token" in tokens

    claims = decode_token(tokens["access_token"])
    assert claims["sub"] == "vpoperations@company.com"
    assert claims["user_uuid"] == str(DEMO_USER_UUIDS["vpoperations@company.com"])
    assert claims["role"] == "vp_operations"


# ============================================================================
# 4. /VERIFY ENDPOINT TESTS
# ============================================================================


def test_verify_endpoint_returns_user_uuid_and_user_id():
    """/api/v1/auth/verify response includes user_uuid and user_id matching database and JWT."""
    client = TestClient(app)
    db: Session = SessionLocal()
    try:
        user = (
            db.query(User).filter(User.email == "warehousemanager@company.com").first()
        )
        assert user is not None

        token = create_access_token(
            {
                "sub": user.email,
                "user_id": user.id,
                "role": user.role.name if user.role else None,
                "user_uuid": str(user.user_uuid),
            }
        )

        response = client.post(
            "/api/v1/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
        data = response.json()

        # Check required fields
        assert data["valid"] is True
        assert data["user_id"] == user.id
        assert isinstance(data["user_id"], int)
        assert data["user_uuid"] == str(user.user_uuid)
        assert uuid.UUID(data["user_uuid"]) == user.user_uuid
        assert data["email"] == user.email
        assert data["role"] == "warehouse_manager"
        assert data["is_active"] is True
        assert "inventory:read" in data["permissions"]

        # Validate with Pydantic VerifyResponse model
        validated = VerifyResponse(**data)
        assert validated.user_uuid == user.user_uuid
        assert validated.user_id == user.id
    finally:
        db.close()


def test_verify_endpoint_cached_response_preserves_user_uuid():
    """Second call to /verify is served from cache and retains user_uuid."""
    client = TestClient(app)
    db: Session = SessionLocal()
    try:
        user = (
            db.query(User).filter(User.email == "complianceofficer@company.com").first()
        )
        assert user is not None

        token = create_access_token(
            {
                "sub": user.email,
                "user_id": user.id,
                "role": user.role.name if user.role else None,
                "user_uuid": str(user.user_uuid),
            }
        )

        first_resp = client.post(
            "/api/v1/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert first_resp.status_code == 200
        first_data = first_resp.json()

        second_resp = client.post(
            "/api/v1/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert second_resp.status_code == 200
        second_data = second_resp.json()

        assert second_data["user_uuid"] == first_data["user_uuid"]
        assert second_data["user_id"] == first_data["user_id"]
        assert second_data["valid"] is True
    finally:
        db.close()


def test_legacy_jwt_without_user_uuid_accepted_by_verify():
    """A valid legacy access token without user_uuid claim is accepted and verify supplies user_uuid."""
    client = TestClient(app)
    db: Session = SessionLocal()
    try:
        user = (
            db.query(User).filter(User.email == "warehousemanager@company.com").first()
        )
        assert user is not None

        # Issue legacy token lacking 'user_uuid' claim (pre-RH5 format)
        legacy_token = create_access_token(
            {
                "sub": user.email,
                "user_id": user.id,
                "role": user.role.name if user.role else None,
            }
        )
        claims = decode_token(legacy_token)
        assert "user_uuid" not in claims

        response = client.post(
            "/api/v1/auth/verify",
            headers={"Authorization": f"Bearer {legacy_token}"},
        )
        assert response.status_code == 200, response.text
        data = response.json()

        # Database user identified correctly and user_uuid supplied from DB
        assert data["valid"] is True
        assert data["user_id"] == user.id
        assert data["user_uuid"] == str(user.user_uuid)
        assert uuid.UUID(data["user_uuid"]) == user.user_uuid
        assert data["email"] == user.email
        assert data["role"] == "warehouse_manager"
        assert data["is_active"] is True
        assert "inventory:read" in data["permissions"]

        # Validate with Pydantic VerifyResponse model
        validated = VerifyResponse(**data)
        assert validated.user_uuid == user.user_uuid
        assert validated.user_id == user.id
    finally:
        db.close()


def test_stale_cached_response_without_user_uuid_evicted_and_refreshed():
    """A stale cache entry without user_uuid is treated as a miss, evicted, and refreshed."""
    from app.core.token_cache import token_cache

    client = TestClient(app)
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "ceo@company.com").first()
        assert user is not None

        token = create_access_token(
            {
                "sub": user.email,
                "user_id": user.id,
                "role": user.role.name if user.role else None,
                "user_uuid": str(user.user_uuid),
            }
        )

        # Pre-populate cache with a stale legacy response dict missing user_uuid
        stale_response = {
            "valid": True,
            "user_id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.name if user.role else None,
            "supplier_id": user.supplier_id,
            "is_active": user.is_active,
            "permissions": ["all:full_access"],
        }
        token_cache.set(token, stale_response, user_id=user.id, ttl_seconds=60)

        # Call /verify - should detect missing user_uuid in cache, evict, and refresh from DB
        response = client.post(
            "/api/v1/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
        data = response.json()

        assert "user_uuid" in data
        assert data["user_uuid"] == str(user.user_uuid)
        assert data["user_id"] == user.id

        # Verify subsequent cache entry now includes user_uuid
        cached_now = token_cache.get(token)
        assert cached_now is not None
        assert "user_uuid" in cached_now
        assert cached_now["user_uuid"] == str(user.user_uuid)
    finally:
        db.close()


def test_verify_endpoint_rejects_invalid_token():
    """Tampered or invalid tokens return 401 Unauthorized."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/verify",
        headers={"Authorization": "Bearer invalid.token.value"},
    )
    assert response.status_code == 401


# ============================================================================
# 5. DEMO USERS DETERMINISTIC UUID TESTS
# ============================================================================


def test_demo_users_receive_deterministic_uuids():
    """All 11 demo accounts have their assigned deterministic UUID in the database."""
    db: Session = SessionLocal()
    try:
        for email, expected_uuid in DEMO_USER_UUIDS.items():
            user = db.query(User).filter(User.email == email).first()
            assert user is not None, f"Demo user '{email}' not found."
            assert user.user_uuid == expected_uuid, (
                f"Demo user '{email}' expected UUID {expected_uuid}, got {user.user_uuid}"
            )
    finally:
        db.close()


def test_repeated_seeding_preserves_demo_uuids():
    """Repeated calls to seed_database() produce identical UUIDs and do not alter existing IDs."""
    db: Session = SessionLocal()
    try:
        initial_states = {
            u.email: (u.id, u.user_uuid)
            for u in db.query(User).filter(User.email.in_(DEMO_USER_UUIDS.keys()))
        }

        # Re-run seeding
        seed_database()

        after_states = {
            u.email: (u.id, u.user_uuid)
            for u in db.query(User).filter(User.email.in_(DEMO_USER_UUIDS.keys()))
        }

        for email, (orig_id, orig_uuid) in initial_states.items():
            after_id, after_uuid = after_states[email]
            assert orig_id == after_id
            assert orig_uuid == after_uuid
    finally:
        db.close()


# ============================================================================
# 6. CONTRACT TESTS
# ============================================================================


def test_platform_verify_contract_json_schema():
    """Verify that contracts/openapi/verify_contract.json matches VerifyResponse schema."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    contract_file = repo_root / "contracts" / "openapi" / "verify_contract.json"
    assert contract_file.exists(), f"Contract file {contract_file} does not exist"

    with open(contract_file, encoding="utf-8") as f:
        schema = json.load(f)

    assert "user_uuid" in schema["required"]
    assert "user_id" in schema["required"]
    assert schema["properties"]["user_uuid"]["type"] == "string"
    assert schema["properties"]["user_uuid"]["format"] == "uuid"
    assert schema["properties"]["user_id"]["type"] == "integer"
    assert schema.get("additionalProperties") is True


def test_real_login_and_verify_consistency_and_contract():
    """Obtain access token via real POST /login, verify token claims against POST /verify,
    and validate the response against the Platform OpenAPI contract schema.
    """
    client = TestClient(app)
    from app.seed import _required_password

    password = _required_password("CEO_PASSWORD")
    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": "ceo@company.com", "password": password},
    )
    assert login_resp.status_code == 200, login_resp.text
    login_data = login_resp.json()
    assert "access_token" in login_data
    token = login_data["access_token"]

    token_claims = decode_token(token)
    assert token_claims["sub"] == "ceo@company.com"
    assert token_claims["user_uuid"] == str(DEMO_USER_UUIDS["ceo@company.com"])

    # Call /api/v1/auth/verify with the real access token
    verify_resp = client.post(
        "/api/v1/auth/verify",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert verify_resp.status_code == 200, verify_resp.text
    verify_data = verify_resp.json()

    # Verify consistency between login token claims and /verify response
    assert verify_data["user_uuid"] == token_claims["user_uuid"]
    assert verify_data["user_id"] == token_claims["user_id"]
    assert verify_data["email"] == token_claims["sub"]
    assert verify_data["role"] == token_claims["role"]
    assert verify_data["valid"] is True

    # Validate against root OpenAPI JSON schema contract
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    contract_file = repo_root / "contracts" / "openapi" / "verify_contract.json"
    assert contract_file.exists(), f"Contract file not found at {contract_file}"
    with open(contract_file, encoding="utf-8") as f:
        contract_schema = json.load(f)

    # 1. Enforce all required fields from contract schema
    for req_field in contract_schema["required"]:
        assert req_field in verify_data, f"Missing required contract field: {req_field}"

    # 2. Enforce field types and formats per contract specification
    assert isinstance(verify_data["valid"], bool)
    assert isinstance(verify_data["user_id"], int) and not isinstance(
        verify_data["user_id"], bool
    )
    assert isinstance(verify_data["user_uuid"], str)
    parsed_uuid = uuid.UUID(verify_data["user_uuid"])
    assert str(parsed_uuid) == verify_data["user_uuid"]
    assert isinstance(verify_data["email"], str) and "@" in verify_data["email"]
    assert isinstance(verify_data["full_name"], str)
    assert isinstance(verify_data["is_active"], bool)
    assert isinstance(verify_data["permissions"], list)
    for p in verify_data["permissions"]:
        assert isinstance(p, str)
    assert verify_data["role"] is None or isinstance(verify_data["role"], str)
    assert verify_data["supplier_id"] is None or isinstance(
        verify_data["supplier_id"], str
    )

    # 3. Validate with Platform's established Pydantic model
    validated_model = VerifyResponse.model_validate(verify_data)
    assert validated_model.valid is True
    assert validated_model.user_id == verify_data["user_id"]
    assert str(validated_model.user_uuid) == verify_data["user_uuid"]

    # 4. Assert Pydantic schema matches the root contract schema
    model_schema = VerifyResponse.model_json_schema()
    for field_name in contract_schema["required"]:
        assert field_name in model_schema["required"]
        assert field_name in model_schema["properties"]


def test_demo_user_uuid_fixup_and_unrelated_user_preservation(monkeypatch):
    """Exercising the real seed_database() resets mismatched demo user UUIDs to deterministic values while preserving unrelated users."""
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(bind=test_engine)

    with TestingSession() as db:
        from app.seed import DEMO_USER_UUIDS, seed_roles

        role_map = seed_roles(db)
        db.commit()

        # Insert a demo user with a wrong random UUID
        wrong_demo_uuid = uuid.uuid4()
        demo_user = User(
            email="ceo@company.com",
            user_uuid=wrong_demo_uuid,
            full_name="CEO",
            password="hashed_pw",
            role_id=role_map["ceo"].id,
            is_active=True,
        )
        # Insert an unrelated normal user with their own UUID
        unrelated_uuid = uuid.uuid4()
        unrelated_user = User(
            email="custom_user@example.com",
            user_uuid=unrelated_uuid,
            full_name="Custom User",
            password="hashed_pw",
            role_id=role_map["analyst"].id,
            is_active=True,
        )
        db.add_all([demo_user, unrelated_user])
        db.commit()

    # Monkeypatch SessionLocal in app.seed to exercise the actual seed_database function
    monkeypatch.setattr("app.seed.SessionLocal", TestingSession)
    from app.seed import seed_database

    seed_database(require_service_keys=False)

    # Verify results on the isolated test database
    with TestingSession() as db:
        refreshed_demo = db.query(User).filter(User.email == "ceo@company.com").first()
        assert refreshed_demo is not None
        assert refreshed_demo.user_uuid == DEMO_USER_UUIDS["ceo@company.com"]

        refreshed_unrelated = (
            db.query(User).filter(User.email == "custom_user@example.com").first()
        )
        assert refreshed_unrelated is not None
        assert refreshed_unrelated.user_uuid == unrelated_uuid
        assert refreshed_unrelated.full_name == "Custom User"
        assert refreshed_unrelated.email == "custom_user@example.com"


def test_sqlite_rebuild_failure_rolls_back_and_preserves_table(monkeypatch):
    """If SQLite table rebuild fails during migration, changes roll back and the original users table remains intact."""
    from sqlalchemy import event
    from sqlalchemy.pool import StaticPool

    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(test_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    with test_engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE users ("
                "id INTEGER PRIMARY KEY, "
                "email VARCHAR(255) NOT NULL, "
                "full_name VARCHAR(255) NOT NULL, "
                "user_uuid CHAR(32)"
                ");"
            )
        )
        conn.execute(
            text(
                "INSERT INTO users (id, email, full_name, user_uuid) VALUES "
                "(1, 'alice@example.com', 'Alice', '0123456789abcdef0123456789abcdef');"
            )
        )

    # Simulate a failure in _rebuild_sqlite_users_table
    import scripts.migrate_add_user_uuid as mig_mod

    def failing_rebuild(conn):
        raise RuntimeError("Disk I/O failure during table swap")

    monkeypatch.setattr(mig_mod, "_rebuild_sqlite_users_table", failing_rebuild)

    with pytest.raises(RuntimeError, match="Disk I/O failure during table swap"):
        mig_mod.run_migration(test_engine)

    # Verify that the original table and rows are preserved
    with test_engine.connect() as conn:
        row = conn.execute(text("SELECT id, email, user_uuid FROM users;")).fetchone()
        assert row is not None
        assert row[0] == 1
        assert row[1] == "alice@example.com"
        assert row[2] == "0123456789abcdef0123456789abcdef"

        # Verify no orphan migration table exists
        mig_table = conn.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='users_migration_new';"
            )
        ).fetchone()
        assert mig_table is None

        # Verify foreign keys are enabled
        fk_on = conn.execute(text("PRAGMA foreign_keys;")).scalar()
        assert fk_on == 1


def test_sqlite_rebuild_preserves_foreign_key_integrity():
    """SQLite table rebuild validates foreign key constraints and preserves relations."""
    test_engine = create_engine("sqlite:///:memory:")
    with test_engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON;"))
        conn.execute(
            text(
                "CREATE TABLE users ("
                "id INTEGER PRIMARY KEY, "
                "email VARCHAR(255) NOT NULL, "
                "user_uuid CHAR(32)"
                ");"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE orders ("
                "id INTEGER PRIMARY KEY, "
                "user_id INTEGER NOT NULL REFERENCES users(id)"
                ");"
            )
        )
        conn.execute(
            text(
                "INSERT INTO users (id, email, user_uuid) VALUES "
                "(1, 'bob@example.com', 'aabbccddeeff00112233445566778899');"
            )
        )
        conn.execute(text("INSERT INTO orders (id, user_id) VALUES (10, 1);"))

    # Run migration
    from scripts.migrate_add_user_uuid import run_migration

    run_migration(test_engine)

    # Verify foreign key check passes and relation holds
    with test_engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON;"))
        violations = conn.execute(text("PRAGMA foreign_key_check;")).fetchall()
        assert len(violations) == 0

        # Verify constraint is actively enforced: inserting invalid FK should fail
        with pytest.raises(IntegrityError):
            conn.execute(text("INSERT INTO orders (id, user_id) VALUES (20, 999);"))


def test_migration_second_run_after_success_is_safe_and_idempotent():
    """A second migration attempt immediately after success succeeds with 0 changes and no stale inspection errors."""
    from scripts.migrate_add_user_uuid import run_migration

    test_engine = create_engine("sqlite:///:memory:")
    with test_engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE users ("
                "id INTEGER PRIMARY KEY, "
                "email VARCHAR(255) NOT NULL, "
                "full_name VARCHAR(255) NOT NULL"
                ");"
            )
        )
        conn.execute(
            text(
                "INSERT INTO users (id, email, full_name) VALUES "
                "(1, 'carol@example.com', 'Carol');"
            )
        )

    # First migration run
    summary1 = run_migration(test_engine)
    assert summary1["column_added"] == 1
    assert summary1["users_backfilled"] == 1
    assert summary1["index_created"] == 1

    # Second migration run: must succeed cleanly without stale schema errors
    summary2 = run_migration(test_engine)
    assert summary2["column_added"] == 0
    assert summary2["users_backfilled"] == 0
    assert summary2["index_created"] == 0

    # Ensure user data is intact
    with test_engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, email, user_uuid FROM users WHERE id = 1;")
        ).fetchone()
        assert row is not None
        assert row[1] == "carol@example.com"
        assert len(row[2]) == 32


def test_postgresql_migration_concurrency_guards(monkeypatch):
    """PostgreSQL migration re-inspects columns and indexes inside the transaction lock, guarding against race conditions."""
    from unittest.mock import Mock

    import sqlalchemy as sa

    from scripts.migrate_add_user_uuid import run_migration

    executed_sql = []

    class MockConnection:
        def execute(self, statement, parameters=None):
            sql = str(statement)
            executed_sql.append(sql.strip())

            class MockResult:
                def fetchall(self):
                    return []

            return MockResult()

    class MockBeginContext:
        def __enter__(self):
            return MockConnection()

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    class MockDialect:
        name = "postgresql"

    class MockEngine:
        dialect = MockDialect()

        def begin(self):
            return MockBeginContext()

    mock_engine = MockEngine()

    pre_lock_inspector = Mock()
    pre_lock_inspector.has_table.return_value = True
    pre_lock_inspector.get_columns.return_value = [{"name": "id"}, {"name": "email"}]

    tx_inspector = Mock()
    tx_inspector.get_columns.return_value = [
        {"name": "id", "nullable": False},
        {"name": "email", "nullable": False},
        {"name": "user_uuid", "nullable": False},
    ]
    tx_inspector.get_indexes.return_value = [{"name": "ix_users_user_uuid"}]

    def mock_inspect(target):
        if isinstance(target, MockConnection):
            return tx_inspector
        return pre_lock_inspector

    monkeypatch.setattr(sa, "inspect", mock_inspect)

    summary = run_migration(mock_engine)
    # Because tx_inspector was used under lock, step 1 was skipped, step 3 was skipped, step 4 was skipped
    assert summary["column_added"] == 0
    assert summary["index_created"] == 0
    # Confirm lock was acquired first
    assert any(
        "LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE" in sql for sql in executed_sql
    )
    # Confirm duplicate ALTER TABLE ADD COLUMN was NOT executed
    assert not any("ADD COLUMN user_uuid" in sql for sql in executed_sql)


def test_init_db_runs_migration_automatically_on_unmigrated_database():
    """init_db creates tables and executes migration automatically before traffic."""
    from app.main import init_db

    test_engine = create_engine("sqlite:///:memory:")

    # Create unmigrated users table (without user_uuid)
    with test_engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE users ("
                "id INTEGER PRIMARY KEY, "
                "email VARCHAR(255) NOT NULL, "
                "full_name VARCHAR(255) NOT NULL"
                ");"
            )
        )
        conn.execute(
            text(
                "INSERT INTO users (id, email, full_name) VALUES "
                "(1, 'existing@example.com', 'Existing User');"
            )
        )

    # Call init_db
    init_db(test_engine)

    # Verify column added, user backfilled, NOT NULL enforced
    with test_engine.connect() as conn:
        col_info = conn.execute(text("PRAGMA table_info(users);")).fetchall()
        user_uuid_col = next(col for col in col_info if col[1] == "user_uuid")
        assert user_uuid_col[3] == 1  # notnull

        row = conn.execute(text("SELECT user_uuid FROM users WHERE id = 1;")).fetchone()
        assert row is not None
        assert row[0] is not None
        assert len(row[0]) == 32


def test_startup_lifespan_fails_if_migration_fails(monkeypatch):
    """Lifespan raises RuntimeError and prevents startup if migration fails."""
    import app.main as main_mod

    def failing_migration(eng):
        raise RuntimeError("Simulated migration failure during deployment")

    monkeypatch.setattr(main_mod, "run_migration", failing_migration)

    with pytest.raises(
        RuntimeError, match="Platform Service database migration failed"
    ):
        import asyncio

        async def run_ls():
            async with main_mod.lifespan(app):
                pass

        asyncio.run(run_ls())


def test_verify_response_accepts_inventory_required_fields():
    """Validate that Platform's own VerifyResponse Pydantic model successfully parses and

    validates a payload containing user_uuid alongside standard verification fields.
    """
    payload = {
        "valid": True,
        "user_id": 42,
        "user_uuid": "00000000-0000-4000-8000-000000000004",
        "email": "procurementmanager@company.com",
        "full_name": "Procurement Manager",
        "role": "procurement_manager",
        "supplier_id": None,
        "is_active": True,
        "permissions": ["procurement:write", "supplier:read"],
    }

    # Verify Platform's Pydantic model parses and validates the payload
    model = VerifyResponse(**payload)
    assert model.user_id == 42
    assert model.user_uuid == uuid.UUID("00000000-0000-4000-8000-000000000004")
    assert str(model.user_uuid) == "00000000-0000-4000-8000-000000000004"
