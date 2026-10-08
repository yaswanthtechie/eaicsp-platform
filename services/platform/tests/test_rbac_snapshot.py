import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.core.dependencies import ROLE_HIERARCHY, require_permission
from app.core.permissions import ROLE_PERMISSIONS

# =========================================================
# Test Helpers
# =========================================================

def fake_user(role: str):
    return SimpleNamespace(
        role=SimpleNamespace(name=role)
    )

# =========================================================
# Fixtures
# =========================================================

PERMISSIONS_V1_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "permissions_v1.json"
)

ROLE_HIERARCHY_V1_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "role_hierarchy_v1.json"
)


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


NEW_ROLES = {
    "platform_admin",
    "procurement_officer",
    "inventory_planner",
    "demand_planner",
    "finance_manager",
    "risk_analyst",
    "data_scientist",
    "auditor",
    "warehouse_operator",
    "carrier",
}


# =========================================================
# Fixture Loaders
# =========================================================

def load_v1_permissions():
    with open(
        PERMISSIONS_V1_PATH,
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


def load_v1_hierarchy():
    with open(
        ROLE_HIERARCHY_V1_PATH,
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


# =========================================================
# Permission Snapshot Tests
# =========================================================

def test_v1_roles_unchanged():
    expected = load_v1_permissions()

    for role, permissions in expected.items():
        assert role in ROLE_PERMISSIONS

        assert set(ROLE_PERMISSIONS[role]) == set(permissions), (
            f"V1 permissions changed for role '{role}'.\n"
            f"Expected: {set(permissions)}\n"
            f"Actual:   {set(ROLE_PERMISSIONS[role])}"
        )


def test_v1_permissions_contain_exactly_the_original_roles():
    expected = load_v1_permissions()

    assert set(expected) == V1_ROLES


# =========================================================
# Auditor Separation-of-Duties Tests
# =========================================================

def test_auditor_denied_on_every_write_permission():
    from app.core.permissions import PERMISSIONS

    write_permissions = {
        permission
        for permission in PERMISSIONS
        if permission.endswith(
            (
                ":write",
                ":create",
                ":approve",
                ":move",
                ":retrain",
                ":promote_staging",
            )
        )
    }

    # Auditor must not have any write-like permission.
    assert not (
        ROLE_PERMISSIONS["auditor"] & write_permissions
    )

    # Auditor must also be rejected by the actual
    # require_permission dependency.
    user = fake_user("auditor")

    for permission in write_permissions:
        checker = require_permission(permission)

        with pytest.raises(HTTPException) as exc:
            checker(user)

        assert exc.value.status_code == 403


# =========================================================
# Role Hierarchy Snapshot Tests
# =========================================================

def test_v1_role_hierarchy_unchanged():
    expected = load_v1_hierarchy()

    actual = {
        role: sorted(ROLE_HIERARCHY[role])
        for role in expected
    }

    expected = {
        role: sorted(roles)
        for role, roles in expected.items()
    }

    assert actual == expected, (
        "V1 role hierarchy changed.\n"
        f"Expected: {expected}\n"
        f"Actual:   {actual}"
    )


def test_v1_hierarchy_contains_exactly_the_original_roles():
    expected = load_v1_hierarchy()

    assert set(expected) == V1_ROLES


def test_new_roles_are_not_in_v1_hierarchy():
    expected = load_v1_hierarchy()

    assert set(expected).isdisjoint(NEW_ROLES)


def test_new_roles_are_not_added_to_v1_hierarchy_permissions():
    for role in V1_ROLES:
        inherited_roles = ROLE_HIERARCHY[role]

        assert not NEW_ROLES.intersection(inherited_roles), (
            f"V1 role '{role}' unexpectedly inherits new roles: "
            f"{NEW_ROLES.intersection(inherited_roles)}"
        )


# =========================================================
# External / New Role Hierarchy Safety
# =========================================================

def test_supplier_cannot_pass_old_admin_hierarchy():
    assert "ceo" not in ROLE_HIERARCHY["supplier"]
    assert "vp_operations" not in ROLE_HIERARCHY["supplier"]


def test_carrier_is_not_in_old_hierarchy():
    assert "carrier" not in ROLE_HIERARCHY