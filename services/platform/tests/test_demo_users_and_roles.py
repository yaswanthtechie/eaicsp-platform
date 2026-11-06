"""Unit and authorization tests for Round 15 Demo Users and Roles (Issue #214).

Validates:
1. All 6 required demo user accounts are seeded with correct roles.
2. Existing seed users are preserved for backward compatibility.
3. Canonical supplier identifiers (SUP-00019, SUP-00021, SUP-00022) are correctly mapped.
4. Passwords are configurable via environment variables and securely hashed (never plaintext).
5. Seeding idempotency: re-running seed_database() produces 0 duplicates, updates missing
   demo fields, preserves user passwords, and does not overwrite unrelated existing users' roles.
6. Flow authorization matrix for the 4 core business operations:
   - Flow A: Approve PO (procurement_manager)
   - Flow B: Goods receipt (warehouse_manager, inventory:write)
   - Flow B: Acknowledge PO (supplier, matching canonical supplier_id)
   - Flow C: View KPIs (ceo, executive domain permissions)
7. Actual Platform authorization dependency enforcement (require_role, require_permission,
   require_permission_or_role) using User objects, verifying 403 Forbidden on unauthorized roles.
"""

import os

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.dependencies import (
    require_permission,
    require_permission_or_role,
    require_role,
)
from app.core.security import hash_password, verify_password
from app.database import SessionLocal
from app.main import app
from app.models.roles import Role
from app.models.users import User
from app.seed import _required_password, seed_database

client = TestClient(app)

REQUIRED_DEMO_USERS = (
    (
        "procurementmanager@company.com",
        "procurement_manager",
        "PROCUREMENT_MANAGER_PASSWORD",
        None,
    ),
    (
        "warehousemanager@company.com",
        "warehouse_manager",
        "WAREHOUSE_MANAGER_PASSWORD",
        None,
    ),
    ("ceo@company.com", "ceo", "CEO_PASSWORD", None),
    ("supplier19@company.com", "supplier", "SUPPLIER_19_PASSWORD", "SUP-00019"),
    ("supplier21@company.com", "supplier", "SUPPLIER_21_PASSWORD", "SUP-00021"),
    ("supplier22@company.com", "supplier", "SUPPLIER_22_PASSWORD", "SUP-00022"),
)

EXISTING_SEED_USERS = (
    ("supplier@company.com", "supplier", "SUP001"),
    ("vpoperations@company.com", "vp_operations", None),
    ("logisticsmanager@company.com", "logistics_manager", None),
    ("complianceofficer@company.com", "compliance_officer", None),
    ("analyst@company.com", "analyst", None),
)


@pytest.fixture
def db_session():
    """Provide a scoped database session for testing models and dependencies."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================
# 1. SEEDING & ACCOUNT EXISTENCE
# ============================================================


def test_all_six_demo_users_seeded():
    """Verify that all six required demo accounts exist and are active in the database."""
    db = SessionLocal()
    try:
        for email, expected_role, _, expected_supplier_id in REQUIRED_DEMO_USERS:
            user = db.query(User).filter(User.email == email).first()
            assert user is not None, (
                f"Demo user '{email}' was not found in the database."
            )
            assert user.is_active is True, f"Demo user '{email}' must be active."
            assert user.role is not None, f"Demo user '{email}' has no assigned role."
            assert user.role.name == expected_role, (
                f"User '{email}' has role '{user.role.name}', expected '{expected_role}'."
            )
            assert user.supplier_id == expected_supplier_id, (
                f"User '{email}' has supplier_id '{user.supplier_id}', expected '{expected_supplier_id}'."
            )
    finally:
        db.close()


def test_existing_seed_users_preserved():
    """Verify that legacy seed users remain intact alongside the new demo accounts."""
    db = SessionLocal()
    try:
        for email, expected_role, expected_supplier_id in EXISTING_SEED_USERS:
            user = db.query(User).filter(User.email == email).first()
            assert user is not None, (
                f"Existing seed user '{email}' was unexpectedly removed."
            )
            assert user.is_active is True
            assert user.role.name == expected_role
            if expected_supplier_id is not None:
                assert user.supplier_id == expected_supplier_id
    finally:
        db.close()


# ============================================================
# 2. CANONICAL SUPPLIER MAPPINGS
# ============================================================


def test_canonical_supplier_mappings():
    """Verify canonical supplier identifiers for Flow B non-sanctioned seed suppliers."""
    db = SessionLocal()
    try:
        suppliers = {
            "supplier19@company.com": "SUP-00019",
            "supplier21@company.com": "SUP-00021",
            "supplier22@company.com": "SUP-00022",
        }
        for email, expected_id in suppliers.items():
            user = db.query(User).filter(User.email == email).first()
            assert user is not None
            assert user.supplier_id == expected_id, (
                f"Expected '{email}' to map to '{expected_id}', got '{user.supplier_id}'."
            )

        # Internal operational roles must not have a supplier_id
        internal_users = (
            "ceo@company.com",
            "warehousemanager@company.com",
            "procurementmanager@company.com",
        )
        for email in internal_users:
            user = db.query(User).filter(User.email == email).first()
            assert user is not None
            assert user.supplier_id is None, (
                f"Internal role '{email}' must not have a supplier_id; found '{user.supplier_id}'."
            )
    finally:
        db.close()


# ============================================================
# 3. PASSWORD SECURITY & HASHING
# ============================================================


def test_passwords_are_hashed_and_not_plaintext():
    """Passwords must be stored as bcrypt hashes, never plaintext, and match env vars."""
    db = SessionLocal()
    try:
        for email, _, env_var, _ in REQUIRED_DEMO_USERS:
            raw_password = os.environ[env_var]
            user = db.query(User).filter(User.email == email).first()
            assert user is not None

            # Must not be stored in plaintext
            assert user.password != raw_password, (
                f"Password for '{email}' appears to be stored in plaintext!"
            )
            # Must be a valid bcrypt hash
            assert user.password.startswith(("$2b$", "$2a$", "$2y$")), (
                f"Password hash for '{email}' is not a bcrypt format hash."
            )
            # Hash must verify against the env var secret
            assert verify_password(raw_password, user.password), (
                f"Stored hash for '{email}' does not match environment variable {env_var}."
            )
    finally:
        db.close()


def test_missing_password_env_var_raises_runtime_error():
    """Calling _required_password raises RuntimeError if environment variable is missing."""
    with pytest.raises(RuntimeError, match="MISSING_PASSWORD_TEST_KEY is not set"):
        _required_password("MISSING_PASSWORD_TEST_KEY")


def test_empty_password_env_var_raises_runtime_error(monkeypatch):
    """A blank value (e.g. copied from .env.example) counts as missing."""
    monkeypatch.setenv("EMPTY_PASSWORD_TEST_KEY", "")
    with pytest.raises(RuntimeError, match="EMPTY_PASSWORD_TEST_KEY is not set"):
        _required_password("EMPTY_PASSWORD_TEST_KEY")


# ============================================================
# 4. AUTHENTICATION & TOKEN VERIFICATION
# ============================================================


def test_demo_users_successful_login_and_token_exchange():
    """All 6 demo accounts can authenticate with their configured passwords."""
    for email, _, env_var, _ in REQUIRED_DEMO_USERS:
        raw_password = os.environ[env_var]
        response = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": raw_password},
        )
        assert response.status_code == 200, (
            f"Login failed for '{email}' with status {response.status_code}: {response.text}"
        )
        body = response.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"


def test_demo_users_verify_endpoint_contracts():
    """Access tokens for demo users verify correctly with expected identity and permissions."""
    for email, expected_role, env_var, expected_supplier_id in REQUIRED_DEMO_USERS:
        raw_password = os.environ[env_var]
        login_resp = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": raw_password},
        )
        token = login_resp.json()["access_token"]

        verify_resp = client.post(
            "/api/v1/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert verify_resp.status_code == 200, (
            f"/verify failed for '{email}': {verify_resp.text}"
        )
        data = verify_resp.json()
        assert data["valid"] is True
        assert data["email"] == email
        assert data["role"] == expected_role
        assert data["supplier_id"] == expected_supplier_id
        assert data["is_active"] is True
        assert isinstance(data["permissions"], list)


# ============================================================
# 5. CORE FLOW OPERATIONS & PERMISSION ENFORCEMENT
# ============================================================


def test_flow_a_po_approval_authorization(db_session):
    """Flow A: PO Approval requires procurement_manager role.

    Inventory service enforces require_roles("procurement_manager") on PO approval.
    Platform RBAC assigns procurement_manager the permissions supplier:read and supplier:write.
    """
    proc_user = (
        db_session.query(User)
        .filter(User.email == "procurementmanager@company.com")
        .first()
    )
    wh_user = (
        db_session.query(User)
        .filter(User.email == "warehousemanager@company.com")
        .first()
    )
    s19_user = (
        db_session.query(User).filter(User.email == "supplier19@company.com").first()
    )

    # 1. Verify Platform permissions via /verify
    proc_pwd = os.environ["PROCUREMENT_MANAGER_PASSWORD"]
    token = client.post(
        "/api/v1/auth/login",
        data={"username": "procurementmanager@company.com", "password": proc_pwd},
    ).json()["access_token"]

    verify = client.post(
        "/api/v1/auth/verify",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert verify["role"] == "procurement_manager"
    assert "supplier:read" in verify["permissions"]
    assert "supplier:write" in verify["permissions"]
    assert "inventory:write" not in verify["permissions"]

    # 2. Test actual Platform role dependency enforcement
    proc_dep = require_role("procurement_manager")
    assert proc_dep(user=proc_user) == proc_user

    # Unauthorized roles must raise 403 Forbidden through Platform dependency
    with pytest.raises(HTTPException) as exc_info:
        proc_dep(user=wh_user)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Forbidden: insufficient permissions"

    with pytest.raises(HTTPException) as exc_info:
        proc_dep(user=s19_user)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Forbidden: insufficient permissions"


def test_flow_b_goods_receipt_authorization(db_session):
    """Flow B: Goods Receipt requires warehouse_manager role with inventory:write permission."""
    wh_user = (
        db_session.query(User)
        .filter(User.email == "warehousemanager@company.com")
        .first()
    )
    proc_user = (
        db_session.query(User)
        .filter(User.email == "procurementmanager@company.com")
        .first()
    )
    s19_user = (
        db_session.query(User).filter(User.email == "supplier19@company.com").first()
    )

    # 1. Verify permissions via /verify
    wh_pwd = os.environ["WAREHOUSE_MANAGER_PASSWORD"]
    token = client.post(
        "/api/v1/auth/login",
        data={"username": "warehousemanager@company.com", "password": wh_pwd},
    ).json()["access_token"]

    verify = client.post(
        "/api/v1/auth/verify",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert verify["role"] == "warehouse_manager"
    assert "inventory:read" in verify["permissions"]
    assert "inventory:write" in verify["permissions"]

    # 2. Test actual Platform permission and role dependency enforcement
    perm_dep = require_permission("inventory:write")
    role_dep = require_role("warehouse_manager")
    dual_dep = require_permission_or_role("inventory:write", "warehouse_manager")

    assert perm_dep(current_user=wh_user) == wh_user
    assert role_dep(user=wh_user) == wh_user
    assert dual_dep(current_user=wh_user) == wh_user

    # Unauthorized roles must raise 403 on inventory:write
    for unauth_user in (proc_user, s19_user):
        with pytest.raises(HTTPException) as exc_info:
            perm_dep(current_user=unauth_user)
        assert exc_info.value.status_code == 403

        with pytest.raises(HTTPException) as exc_info:
            role_dep(user=unauth_user)
        assert exc_info.value.status_code == 403


def test_flow_b_supplier_po_acknowledgement_and_verified_identity(db_session):
    """Flow B: Supplier PO acknowledgement requires role supplier and verified supplier_id.

    Platform provides authenticated identity and verified supplier_id (SUP-00019, SUP-00021, SUP-00022).
    Cross-supplier PO ownership checks (user["supplier_id"] == po.supplier_id) are enforced
    downstream by the Supplier Portal service, not by Platform.
    """
    s19_user = (
        db_session.query(User).filter(User.email == "supplier19@company.com").first()
    )
    s21_user = (
        db_session.query(User).filter(User.email == "supplier21@company.com").first()
    )
    s22_user = (
        db_session.query(User).filter(User.email == "supplier22@company.com").first()
    )
    wh_user = (
        db_session.query(User)
        .filter(User.email == "warehousemanager@company.com")
        .first()
    )
    proc_user = (
        db_session.query(User)
        .filter(User.email == "procurementmanager@company.com")
        .first()
    )

    # 1. Test role dependency enforcement
    supplier_dep = require_role("supplier")
    assert supplier_dep(user=s19_user) == s19_user
    assert supplier_dep(user=s21_user) == s21_user
    assert supplier_dep(user=s22_user) == s22_user

    # Internal users must raise 403 on require_role("supplier")
    with pytest.raises(HTTPException) as exc_info:
        supplier_dep(user=wh_user)
    assert exc_info.value.status_code == 403

    with pytest.raises(HTTPException) as exc_info:
        supplier_dep(user=proc_user)
    assert exc_info.value.status_code == 403

    # 2. Verify all 3 supplier identities and supplier_id attributes via /verify
    supplier_credentials = (
        ("supplier19@company.com", "SUPPLIER_19_PASSWORD", "SUP-00019"),
        ("supplier21@company.com", "SUPPLIER_21_PASSWORD", "SUP-00021"),
        ("supplier22@company.com", "SUPPLIER_22_PASSWORD", "SUP-00022"),
    )
    for email, pwd_key, expected_supplier_id in supplier_credentials:
        pwd = os.environ[pwd_key]
        tok = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": pwd},
        ).json()["access_token"]
        ver = client.post(
            "/api/v1/auth/verify",
            headers={"Authorization": f"Bearer {tok}"},
        ).json()
        assert ver["role"] == "supplier"
        assert ver["supplier_id"] == expected_supplier_id
        assert "supplier:read" in ver["permissions"]
        assert "supplier:write" in ver["permissions"]


def test_flow_c_view_kpis_authorization(db_session):
    """Flow C: CEO has executive visibility across inventory, compliance, supplier, and logistics."""
    ceo_user = db_session.query(User).filter(User.email == "ceo@company.com").first()
    proc_user = (
        db_session.query(User)
        .filter(User.email == "procurementmanager@company.com")
        .first()
    )
    wh_user = (
        db_session.query(User)
        .filter(User.email == "warehousemanager@company.com")
        .first()
    )
    s19_user = (
        db_session.query(User).filter(User.email == "supplier19@company.com").first()
    )

    # 1. Verify CEO /verify response contains all required KPI permissions
    ceo_pwd = os.environ["CEO_PASSWORD"]
    token = client.post(
        "/api/v1/auth/login",
        data={"username": "ceo@company.com", "password": ceo_pwd},
    ).json()["access_token"]

    verify = client.post(
        "/api/v1/auth/verify",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert verify["role"] == "ceo"
    required_kpi_permissions = {
        "inventory:read",
        "compliance:read",
        "supplier:read",
        "logistics:read",
    }
    assert required_kpi_permissions.issubset(set(verify["permissions"]))

    # 2. Test actual Platform authorization dependencies
    ceo_role_dep = require_role("ceo")
    assert ceo_role_dep(user=ceo_user) == ceo_user

    # Non-CEO roles cannot satisfy require_role("ceo")
    for unauth_user in (proc_user, wh_user, s19_user):
        with pytest.raises(HTTPException) as exc_info:
            ceo_role_dep(user=unauth_user)
        assert exc_info.value.status_code == 403

    # Restricted domain permissions
    comp_dep = require_permission("compliance:read")
    log_dep = require_permission("logistics:read")

    assert comp_dep(current_user=ceo_user) == ceo_user
    assert log_dep(current_user=ceo_user) == ceo_user

    # Unauthorized roles must raise 403 on restricted permissions
    with pytest.raises(HTTPException) as exc_info:
        comp_dep(current_user=s19_user)
    assert exc_info.value.status_code == 403

    with pytest.raises(HTTPException) as exc_info:
        comp_dep(current_user=wh_user)
    assert exc_info.value.status_code == 403

    with pytest.raises(HTTPException) as exc_info:
        log_dep(current_user=proc_user)
    assert exc_info.value.status_code == 403


# ============================================================
# 6. SEEDING IDEMPOTENCY & SAFETY
# ============================================================


def test_seeding_idempotency_does_not_create_duplicates():
    """Re-running seed_database() creates no duplicates and maintains user record integrity."""
    db = SessionLocal()
    try:
        count_before = db.query(User).count()
        role_count_before = db.query(Role).count()
    finally:
        db.close()

    seed_database()

    db = SessionLocal()
    try:
        count_after = db.query(User).count()
        role_count_after = db.query(Role).count()
        assert count_after == count_before
        assert role_count_after == role_count_before
    finally:
        db.close()


def test_seeding_preserves_user_modified_passwords():
    """Re-running seed_database() must not overwrite or reset user-modified passwords."""
    test_user_email = "supplier22@company.com"
    new_custom_password = "UserUpdatedPassword!456"
    original_password_hash = None

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == test_user_email).first()
        assert user is not None
        original_password_hash = user.password
        user.password = hash_password(new_custom_password)
        db.commit()
    finally:
        db.close()

    try:
        seed_database()

        login_resp = client.post(
            "/api/v1/auth/login",
            data={"username": test_user_email, "password": new_custom_password},
        )
        assert login_resp.status_code == 200
    finally:
        # Restore default seed password even if seed_database or assertion fails
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == test_user_email).first()
            if user is not None:
                user.password = (
                    original_password_hash
                    if original_password_hash is not None
                    else hash_password(os.environ["SUPPLIER_22_PASSWORD"])
                )
                db.commit()
        finally:
            db.close()


def test_seeding_updates_missing_demo_fields():
    """Re-running seed_database() restores missing supplier_id or role without resetting password."""
    test_user_email = "supplier19@company.com"
    original_supplier_id = None
    original_full_name = None

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == test_user_email).first()
        assert user is not None
        original_supplier_id = user.supplier_id
        original_full_name = user.full_name
        user.supplier_id = None
        user.full_name = "Temporary Outdated Name"
        db.commit()
    finally:
        db.close()

    try:
        seed_database()

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == test_user_email).first()
            assert user.supplier_id == "SUP-00019"
            assert user.full_name == "Unity Manufacturing Supplier"
        finally:
            db.close()
    finally:
        # Restore exact original values even if seed_database or assertion fails
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == test_user_email).first()
            if user is not None:
                user.supplier_id = original_supplier_id
                user.full_name = original_full_name
                db.commit()
        finally:
            db.close()


def test_seeding_does_not_overwrite_unrelated_existing_users_roles():
    """seed_database() must preserve custom roles on non-demo existing users."""
    target_email = "analyst@company.com"
    original_role_id = None

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == target_email).first()
        assert user is not None
        original_role_id = user.role_id
        risk_role = db.query(Role).filter(Role.name == "risk_analyst").first()
        assert risk_role is not None
        user.role_id = risk_role.id
        db.commit()
    finally:
        db.close()

    try:
        seed_database()

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == target_email).first()
            risk_role = db.query(Role).filter(Role.name == "risk_analyst").first()
            assert user.role_id == risk_role.id, (
                "Non-demo user role was overwritten during seeding!"
            )

            # Dedicated demo accounts still maintain their assigned roles
            proc = (
                db.query(User)
                .filter(User.email == "procurementmanager@company.com")
                .first()
            )
            assert proc.role.name == "procurement_manager"
        finally:
            db.close()
    finally:
        # Restore original role even if seeding or assertions fail
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == target_email).first()
            if user is not None and original_role_id is not None:
                user.role_id = original_role_id
                db.commit()
        finally:
            db.close()


def test_seeding_restores_demo_user_role():
    """Re-running seed_database() puts a demo account's role back."""
    test_user_email = "warehousemanager@company.com"
    original_role_id = None

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == test_user_email).first()
        analyst_role = db.query(Role).filter(Role.name == "analyst").first()
        assert user is not None
        assert analyst_role is not None
        original_role_id = user.role_id
        user.role_id = analyst_role.id
        db.commit()
    finally:
        db.close()

    try:
        seed_database()

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == test_user_email).first()
            role = db.query(Role).filter(Role.id == user.role_id).first()
            assert role.name == "warehouse_manager"
        finally:
            db.close()
    finally:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == test_user_email).first()
            if user is not None and original_role_id is not None:
                user.role_id = original_role_id
                db.commit()
        finally:
            db.close()
