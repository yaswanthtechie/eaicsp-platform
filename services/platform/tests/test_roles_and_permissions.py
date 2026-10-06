import json
from pathlib import Path
import pytest
from app.core.permissions import ROLE_PERMISSIONS
from app.schemas.user import Role

# ============================================================
# Fixtures / Constants
# ============================================================

FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "permissions_v1.json"
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


V2_ROLES = {
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


NEW_ROLE_EXPECTED_PERMISSIONS = {
    "platform_admin": {
        "audit:read",
        "user:read",
        "user:manage",
        "role:assign",
    },
    "procurement_officer": {
        "purchase_order:create",
        "purchase_order:read",
        "supplier:read",
    },
    "inventory_planner": {
        "inventory:read",
        "inventory:plan",
    },
    "demand_planner": {
        "demand:read",
        "demand:write",
        "inventory:read",
    },
    "finance_manager": {
        "invoice:read",
        "invoice:approve",
        "payment:approve",
    },
    "risk_analyst": {
        "supplier:read",
        "risk:read",
    },
    "data_scientist": {
        "model:read",
        "model:retrain",
        "model:promote_staging",
    },
    "auditor": {
        "audit:read",
        "inventory:read",
        "compliance:read",
        "supplier:read",
        "logistics:read",
        "purchase_order:read",
        "invoice:read",
        "risk:read",
        "model:read",
        "demand:read",
    },
    "warehouse_operator": {
        "inventory:read",
        "inventory:move",
    },
    "carrier": {
        "shipment:read",
    },
}


# ============================================================
# 1. Role Model Tests
# ============================================================

def test_v1_role_values_unchanged():
    """Existing V1 role strings must never change."""

    actual_v1_values = {
        role.value
        for role in Role
        if role.value in V1_ROLES
    }

    assert actual_v1_values == V1_ROLES


def test_all_expected_roles_exist():
    """All 8 V1 + 10 V2 roles must exist."""

    expected_roles = V1_ROLES | V2_ROLES
    actual_roles = {role.value for role in Role}

    assert expected_roles.issubset(actual_roles)
    assert len(actual_roles) >= 18


def test_every_enum_role_has_permission_mapping():
    """Every Role enum value must have a permission mapping."""

    enum_roles = {role.value for role in Role}
    mapped_roles = set(ROLE_PERMISSIONS.keys())

    assert enum_roles == mapped_roles


def test_every_permission_is_known():
    """No role may reference a permission absent from PERMISSIONS."""

    from app.core.permissions import PERMISSIONS

    for role, permissions in ROLE_PERMISSIONS.items():
        unknown = set(permissions) - PERMISSIONS

        assert not unknown, (
            f"Role '{role}' contains unknown permissions: {unknown}"
        )


# ============================================================
# 2. New Role Existence / Exact Permission Tests
# ============================================================

def test_all_new_roles_exist():
    """All ten V2 roles must exist."""

    for role in V2_ROLES:
        assert role in ROLE_PERMISSIONS


def test_new_role_permissions_are_exact():
    """Every V2 role must have exactly its approved permissions."""

    for role, expected_permissions in NEW_ROLE_EXPECTED_PERMISSIONS.items():
        assert ROLE_PERMISSIONS[role] == expected_permissions, (
            f"Unexpected permissions for role '{role}'.\n"
            f"Expected: {expected_permissions}\n"
            f"Actual:   {ROLE_PERMISSIONS[role]}"
        )


# ============================================================
# 3. One ALLOWED Permission Test for Every New Role
# ============================================================

@pytest.mark.parametrize(
    "role,permission",
    [
        ("platform_admin", "user:manage"),
        ("procurement_officer", "purchase_order:create"),
        ("inventory_planner", "inventory:plan"),
        ("demand_planner", "demand:write"),
        ("finance_manager", "payment:approve"),
        ("risk_analyst", "risk:read"),
        ("data_scientist", "model:retrain"),
        ("auditor", "audit:read"),
        ("warehouse_operator", "inventory:move"),
        ("carrier", "shipment:read"),
    ],
)
def test_new_role_has_allowed_permission(role, permission):
    assert permission in ROLE_PERMISSIONS[role]


# ============================================================
# 4. One DENIED Permission Test for Every New Role
# ============================================================

@pytest.mark.parametrize(
    "role,permission",
    [
        ("platform_admin", "inventory:write"),
        ("procurement_officer", "payment:approve"),
        ("inventory_planner", "invoice:approve"),
        ("demand_planner", "role:assign"),
        ("finance_manager", "inventory:write"),
        ("risk_analyst", "model:retrain"),
        ("data_scientist", "payment:approve"),
        ("auditor", "inventory:write"),
        ("warehouse_operator", "purchase_order:create"),
        ("carrier", "user:manage"),
    ],
)
def test_new_role_denies_unrelated_permission(role, permission):
    assert permission not in ROLE_PERMISSIONS[role]


# ============================================================
# 5. Platform Admin Tests
# ============================================================

def test_platform_admin_has_no_business_data_permissions():
    """Platform admin must not receive business-data permissions."""

    business_permissions = {
        "inventory:read",
        "inventory:write",
        "inventory:plan",
        "inventory:move",
        "supplier:read",
        "supplier:write",
        "logistics:read",
        "logistics:write",
        "shipment:read",
        "purchase_order:create",
        "purchase_order:read",
        "purchase_order:approve",
        "demand:read",
        "demand:write",
        "invoice:read",
        "invoice:approve",
        "payment:approve",
        "risk:read",
        "model:read",
        "model:retrain",
        "model:promote_staging",
        "model:promote_production",
    }

    assert ROLE_PERMISSIONS["platform_admin"].isdisjoint(
        business_permissions
    )


def test_platform_admin_can_manage_platform_users_and_roles():
    expected = {
        "audit:read",
        "user:read",
        "user:manage",
        "role:assign",
    }

    assert ROLE_PERMISSIONS["platform_admin"] == expected


# ============================================================
# 6. Inventory / Warehouse Permission Tests
# ============================================================

def test_warehouse_operator_uses_inventory_move():
    permissions = ROLE_PERMISSIONS["warehouse_operator"]

    assert "inventory:move" in permissions
    assert "stock:move" not in permissions


def test_stock_move_permission_removed():
    """Legacy stock:move must not be assigned to any role."""

    for role, permissions in ROLE_PERMISSIONS.items():
        assert "stock:move" not in permissions, (
            f"Legacy stock:move still exists for role '{role}'"
        )


# ============================================================
# 7. Auditor Read-Only Tests
# ============================================================

def test_auditor_has_no_write_permissions():
    auditor_permissions = ROLE_PERMISSIONS["auditor"]

    write_permissions = {
        "inventory:write",
        "inventory:move",
        "supplier:write",
        "logistics:write",
        "demand:write",
        "purchase_order:create",
        "purchase_order:approve",
        "invoice:approve",
        "payment:approve",
        "model:retrain",
        "model:promote_staging",
        "model:promote_production",
        "user:manage",
        "role:assign",
    }

    assert auditor_permissions.isdisjoint(write_permissions)


# ============================================================
# 8. External Role Tests
# ============================================================

def test_carrier_has_only_shipment_read():
    assert ROLE_PERMISSIONS["carrier"] == {
        "shipment:read",
    }


def test_supplier_has_no_internal_permissions():
    """
    Existing supplier role must not receive internal
    platform/business-management permissions.
    """

    supplier_permissions = ROLE_PERMISSIONS["supplier"]

    internal_permissions = {
        "user:read",
        "user:manage",
        "role:assign",
        "audit:read",
        "inventory:read",
        "inventory:write",
        "inventory:plan",
        "inventory:move",
        "logistics:read",
        "logistics:write",
        "shipment:read",
        "purchase_order:create",
        "purchase_order:read",
        "purchase_order:approve",
        "invoice:read",
        "invoice:approve",
        "payment:approve",
        "risk:read",
        "model:read",
        "model:retrain",
        "model:promote_staging",
        "model:promote_production",
    }

    assert supplier_permissions.isdisjoint(internal_permissions)