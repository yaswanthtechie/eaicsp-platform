import os
import uuid
import pytest
from fastapi.testclient import TestClient
from app.core.permissions import ROLE_PERMISSIONS
from app.main import app
from app.schemas.user import Role
from app.seed import ROLES

# =============================================================
# TEST CLIENT
# =============================================================
client = TestClient(app)
# =============================================================
# ROLE DEFINITIONS
# =============================================================

V1_ROLES = {
    "ceo",
    "vp_operations",
    "procurement_manager",
    "logistics_manager",
    "compliance_officer",
    "warehouse_manager",
    "analyst",
    "supplier",
}

NEW_ROLES = sorted(
    role.value
    for role in Role
    if role.value not in V1_ROLES
)

# =============================================================
# TEST DATA
# =============================================================
TEST_PASSWORD = "TestUser@12345"
# =============================================================
# /VERIFY RESPONSE CONTRACT
# =============================================================

VERIFY_KEYS = {
    "valid",
    "user_id",
    "email",
    "full_name",
    "role",
    "supplier_id",
    "is_active",
    "permissions",
}

# =============================================================
# HELPERS
# =============================================================

def _login(email: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )

    assert response.status_code == 200, response.text

    return response.json()["access_token"]


def _auth(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}"
    }


def _create_user(admin_token: str, role: str) -> tuple[str, dict]:
    email = f"{role}.{uuid.uuid4().hex[:8]}@company.com"

    response = client.post(
        "/api/v1/admin/users",
        headers=_auth(admin_token),
        json={
            "email": email,
            "full_name": f"Test {role}",
            "password": TEST_PASSWORD,
            "role": role,
        },
    )

    assert response.status_code == 201, response.text

    return email, response.json()

# =============================================================
# Every Role enum value must be present in ROLES
# =============================================================

def test_every_enum_role_is_seeded():
    """
    If a role is in the API enum, it must also exist in the
    seed role catalogue.
    """

    assert {name for name, _ in ROLES} == {
        role.value for role in Role
    }

# =============================================================
# At least 15 roles must exist
# =============================================================

def test_there_are_at_least_15_roles():
    assert len(ROLES) >= 15

# =============================================================
# Every new role can be assigned and verified
# =============================================================

@pytest.mark.parametrize("role", NEW_ROLES)
def test_new_role_can_be_assigned_and_verified(role):
    """
    Verify every new Round 12+13 role can be assigned and then
    successfully verified through /auth/verify.

    Also pins the exact /verify response contract.
    """

    ceo_token = _login(
        "ceo@company.com",
        os.environ["CEO_PASSWORD"],
    )

    email, _ = _create_user(
        ceo_token,
        role,
    )

    user_token = _login(
        email,
        TEST_PASSWORD,
    )

    response = client.post(
        "/api/v1/auth/verify",
        headers=_auth(user_token),
    )

    assert response.status_code == 200, response.text

    body = response.json()

    # ---------------------------------------------------------
    # exact /verify response keys
    # ---------------------------------------------------------

    assert set(body) == VERIFY_KEYS

    # ---------------------------------------------------------
    # Verify role and permissions
    # ---------------------------------------------------------

    assert body["role"] == role

    assert body["permissions"] == sorted(
        ROLE_PERMISSIONS[role]
    )


# =============================================================
# Existing V1 /verify contract must remain unchanged
# =============================================================

@pytest.mark.parametrize(
    "email, password_env, role",
    [
        (
            "ceo@company.com",
            "CEO_PASSWORD",
            "ceo",
        ),
        (
            "supplier@company.com",
            "SUPPLIER_PASSWORD",
            "supplier",
        ),
    ],
)
def test_verify_response_contract_is_unchanged(
    email,
    password_env,
    role,
):
    """
    Pin the existing /verify response contract used by
    downstream microservices.

    The response must contain exactly:

        valid
        user_id
        email
        full_name
        role
        supplier_id
        is_active
        permissions
    """

    token = _login(
        email,
        os.environ[password_env],
    )

    response = client.post(
        "/api/v1/auth/verify",
        headers=_auth(token),
    )

    assert response.status_code == 200, response.text

    body = response.json()

    # ---------------------------------------------------------
    # Exact response shape
    # ---------------------------------------------------------

    assert set(body) == VERIFY_KEYS

    # ---------------------------------------------------------
    # Response values
    # ---------------------------------------------------------

    assert body["valid"] is True

    assert isinstance(
        body["user_id"],
        int,
    )

    assert body["email"] == email

    assert isinstance(
        body["full_name"],
        str,
    )

    assert body["role"] == role

    assert body["is_active"] is True

    assert body["permissions"] == sorted(
        ROLE_PERMISSIONS[role]
    )

# =============================================================
# Existing user can be moved to a new role
# =============================================================

def test_existing_user_can_be_moved_to_a_new_role():
    """
    Verify that an existing user can be changed from an existing
    role to a newly introduced Round 12+13 role.
    """

    ceo_token = _login(
        "ceo@company.com",
        os.environ["CEO_PASSWORD"],
    )

    _, created = _create_user(
        ceo_token,
        "analyst",
    )

    response = client.patch(
        f"/api/v1/admin/users/{created['user_id']}/role",
        headers=_auth(ceo_token),
        json={
            "role": "auditor",
        },
    )

    assert response.status_code == 200, response.text

# =============================================================
# platform_admin can create users, analyst cannot
# =============================================================

def test_platform_admin_can_create_user_but_analyst_cannot():
    """
    platform_admin has user:manage and therefore can create users.

    analyst does not have user:manage and is not CEO/VP, so the
    same operation must return 403.
    """

    # ---------------------------------------------------------
    # Create test users as CEO
    # ---------------------------------------------------------

    ceo_token = _login(
        "ceo@company.com",
        os.environ["CEO_PASSWORD"],
    )

    platform_admin_email, _ = _create_user(
        ceo_token,
        "platform_admin",
    )

    analyst_email, _ = _create_user(
        ceo_token,
        "analyst",
    )

    # ---------------------------------------------------------
    # platform_admin -> POST /admin/users -> 201
    # ---------------------------------------------------------

    platform_admin_token = _login(
        platform_admin_email,
        TEST_PASSWORD,
    )

    created_email = (
        f"platform-admin-created-"
        f"{uuid.uuid4().hex[:8]}@company.com"
    )

    response = client.post(
        "/api/v1/admin/users",
        headers=_auth(platform_admin_token),
        json={
            "email": created_email,
            "full_name": "Created By Platform Admin",
            "password": TEST_PASSWORD,
            "role": "analyst",
        },
    )

    assert response.status_code == 201, response.text

    # ---------------------------------------------------------
    # analyst -> POST /admin/users -> 403
    # ---------------------------------------------------------

    analyst_token = _login(
        analyst_email,
        TEST_PASSWORD,
    )

    response = client.post(
        "/api/v1/admin/users",
        headers=_auth(analyst_token),
        json={
            "email": (
                f"analyst-attempt-"
                f"{uuid.uuid4().hex[:8]}@company.com"
            ),
            "full_name": "Should Not Be Created",
            "password": TEST_PASSWORD,
            "role": "analyst",
        },
    )

    assert response.status_code == 403, response.text
