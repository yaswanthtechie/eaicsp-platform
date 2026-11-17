import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.security import hash_password
from app.database import Base, SessionLocal, engine
from app.models.roles import Role
from app.models.users import User

ROLES = [
    # ---- V1 roles (unchanged) ----
    ("ceo", "Chief Executive Officer"),
    ("vp_operations", "VP Operations"),
    ("procurement_manager", "Procurement Manager"),
    ("logistics_manager", "Logistics Manager"),
    ("compliance_officer", "Compliance Officer"),
    ("warehouse_manager", "Warehouse Manager"),
    ("analyst", "Analyst"),
    ("supplier", "Supplier"),
    # ---- V2 roles (Round 12+13) ----
    ("platform_admin", "Platform Administrator"),
    ("procurement_officer", "Procurement Officer"),
    ("inventory_planner", "Inventory Planner"),
    ("demand_planner", "Demand Planner"),
    ("finance_manager", "Finance Manager"),
    ("risk_analyst", "Risk Analyst"),
    ("data_scientist", "Data Scientist"),
    ("auditor", "Auditor"),
    ("warehouse_operator", "Warehouse Operator"),
    ("carrier", "Carrier"),
]

REQUIRED_SERVICE_KEYS = {
    "inventory": "INVENTORY_SERVICE_API_KEY",
    "supplier-portal": "SUPPLIER_PORTAL_SERVICE_API_KEY",
    "gateway-bff": "GATEWAY_BFF_SERVICE_API_KEY",
    "forecast-serving": "FORECAST_SERVING_SERVICE_API_KEY",
}

DEDICATED_DEMO_EMAILS = {
    "procurementmanager@company.com",
    "warehousemanager@company.com",
    "ceo@company.com",
    "supplier19@company.com",
    "supplier21@company.com",
    "supplier22@company.com",
}

DEMO_USER_UUIDS: dict[str, uuid.UUID] = {
    "ceo@company.com": uuid.UUID("00000000-0000-4000-8000-000000000001"),
    "warehousemanager@company.com": uuid.UUID("00000000-0000-4000-8000-000000000002"),
    "vpoperations@company.com": uuid.UUID("00000000-0000-4000-8000-000000000003"),
    "procurementmanager@company.com": uuid.UUID("00000000-0000-4000-8000-000000000004"),
    "logisticsmanager@company.com": uuid.UUID("00000000-0000-4000-8000-000000000005"),
    "complianceofficer@company.com": uuid.UUID("00000000-0000-4000-8000-000000000006"),
    "supplier@company.com": uuid.UUID("00000000-0000-4000-8000-000000000007"),
    "analyst@company.com": uuid.UUID("00000000-0000-4000-8000-000000000008"),
    "supplier19@company.com": uuid.UUID("00000000-0000-4000-8000-000000000019"),
    "supplier21@company.com": uuid.UUID("00000000-0000-4000-8000-000000000021"),
    "supplier22@company.com": uuid.UUID("00000000-0000-4000-8000-000000000022"),
}


def _required_password(env_var: str) -> str:
    """
    Read a seed password from the environment.

    Raises at call time (not import time) so that importing this module
    -- as the test suite does -- never requires the full set of seed
    passwords to be present.
    """
    value = os.environ.get(env_var, "")
    if not value.strip():
        raise RuntimeError(
            f"{env_var} is not set. Seed passwords must be supplied via "
            f"environment variables; see .env.example."
        )
    return value


def get_seed_users() -> list[dict[str, Any]]:
    users: list[dict[str, Any]] = [
        {
            "email": "ceo@company.com",
            "full_name": "Company CEO",
            "password": _required_password("CEO_PASSWORD"),
            "role": "ceo",
        },
        {
            "email": "warehousemanager@company.com",
            "full_name": "Warehouse Manager",
            "password": _required_password("WAREHOUSE_MANAGER_PASSWORD"),
            "role": "warehouse_manager",
        },
        {
            "email": "vpoperations@company.com",
            "full_name": "VP Operations",
            "password": _required_password("VP_OPERATIONS_PASSWORD"),
            "role": "vp_operations",
        },
        {
            "email": "procurementmanager@company.com",
            "full_name": "Procurement Manager",
            "password": _required_password("PROCUREMENT_MANAGER_PASSWORD"),
            "role": "procurement_manager",
        },
        {
            "email": "logisticsmanager@company.com",
            "full_name": "Logistics Manager",
            "password": _required_password("LOGISTICS_MANAGER_PASSWORD"),
            "role": "logistics_manager",
        },
        {
            "email": "complianceofficer@company.com",
            "full_name": "Compliance Officer",
            "password": _required_password("COMPLIANCE_OFFICER_PASSWORD"),
            "role": "compliance_officer",
        },
        {
            "email": "supplier@company.com",
            "full_name": "Supplier",
            "password": _required_password("SUPPLIER_PASSWORD"),
            "role": "supplier",
            "supplier_id": "SUP001",
        },
        {
            "email": "analyst@company.com",
            "full_name": "Analyst",
            "password": _required_password("ANALYST_PASSWORD"),
            "role": "analyst",
        },
        {
            "email": "supplier19@company.com",
            "full_name": "Unity Manufacturing Supplier",
            "password": _required_password("SUPPLIER_19_PASSWORD"),
            "role": "supplier",
            "supplier_id": "SUP-00019",
        },
        {
            "email": "supplier21@company.com",
            "full_name": "Evergreen Supplies Supplier",
            "password": _required_password("SUPPLIER_21_PASSWORD"),
            "role": "supplier",
            "supplier_id": "SUP-00021",
        },
        {
            "email": "supplier22@company.com",
            "full_name": "Bluepeak Enterprises Supplier",
            "password": _required_password("SUPPLIER_22_PASSWORD"),
            "role": "supplier",
            "supplier_id": "SUP-00022",
        },
    ]

    for user in users:
        email = user["email"].lower()
        if email in DEMO_USER_UUIDS:
            user["user_uuid"] = DEMO_USER_UUIDS[email]

    return users


def seed_roles(db) -> dict:
    """Insert any missing roles. Safe to run again on an existing database.

    Flushes but does NOT commit: the caller must call db.commit().
    """
    role_map = {}

    for role_name, description in ROLES:
        role = db.query(Role).filter(Role.name == role_name).first()

        if role is None:
            role = Role(name=role_name, description=description)
            db.add(role)
            db.flush()

        role_map[role_name] = role

    return role_map


def seed_service_api_keys(db, *, require_env: bool = False) -> dict[str, str]:
    """Create or re-use the Platform-issued service identities for caller services."""
    from app.core.service_auth import generate_service_api_key, hash_service_api_key
    from app.models.service_api_keys import ServiceAPIKey

    missing = [
        env_name
        for env_name in REQUIRED_SERVICE_KEYS.values()
        if not os.getenv(env_name)
    ]
    if require_env and missing:
        raise RuntimeError(
            "Missing required service API-key environment variables: "
            + ", ".join(missing)
        )

    created: dict[str, str] = {}

    for service_name, env_name in REQUIRED_SERVICE_KEYS.items():
        raw_key = os.getenv(env_name)
        if not raw_key:
            raw_key = generate_service_api_key()

        existing = (
            db.query(ServiceAPIKey)
            .filter(ServiceAPIKey.service_name == service_name)
            .first()
        )

        if existing is not None:
            if not existing.is_active:
                # Never undo an admin revoke. Re-issue via POST /api/v1/admin/service-keys.
                print(f"Skipping '{service_name}': key is revoked.")
                continue
            env_key = os.getenv(env_name)
            if env_key:
                expected_hash = hash_service_api_key(env_key)
                if existing.key_hash != expected_hash:
                    existing.key_hash = expected_hash
                created[service_name] = env_key
            continue

        db.add(
            ServiceAPIKey(
                service_name=service_name,
                key_hash=hash_service_api_key(raw_key),
                is_active=True,
                expires_at=None,
            )
        )
        created[service_name] = raw_key

    db.commit()
    return created


def seed_database(require_service_keys: bool = False):
    db = SessionLocal()

    try:
        # ----------------------------------------
        # Create roles
        # ----------------------------------------
        role_map = seed_roles(db)
        # ----------------------------------------
        # Create users
        # ----------------------------------------

        for data in get_seed_users():
            email = data["email"].lower()

            existing_user = db.query(User).filter(User.email == email).first()

            if existing_user:
                if email in DEDICATED_DEMO_EMAILS:
                    # Keep dedicated demo accounts correctly configured
                    target_role_id = role_map[data["role"]].id
                    if existing_user.role_id != target_role_id:
                        print(
                            f"Resetting demo account '{email}' to role '{data['role']}'."
                        )
                        existing_user.role_id = target_role_id
                    target_supplier_id = data.get("supplier_id")
                    if target_supplier_id != existing_user.supplier_id:
                        existing_user.supplier_id = target_supplier_id
                    if (
                        data.get("full_name")
                        and existing_user.full_name != data["full_name"]
                    ):
                        existing_user.full_name = data["full_name"]
                    expected_uuid = data.get("user_uuid")
                    if expected_uuid and existing_user.user_uuid != expected_uuid:
                        existing_user.user_uuid = expected_uuid
                else:
                    # Avoid unexpectedly changing unrelated existing users' roles
                    if existing_user.role_id is None:
                        existing_user.role_id = role_map[data["role"]].id
                    if existing_user.supplier_id is None and data.get("supplier_id"):
                        existing_user.supplier_id = data.get("supplier_id")
                    expected_uuid = data.get("user_uuid")
                    if expected_uuid and existing_user.user_uuid != expected_uuid:
                        existing_user.user_uuid = expected_uuid
                continue
            now = datetime.now(UTC)

            user = User(
                email=email,
                user_uuid=data.get("user_uuid") or uuid.uuid4(),
                full_name=data["full_name"],
                password=hash_password(data["password"]),
                role_id=role_map[data["role"]].id,
                supplier_id=data.get("supplier_id"),
                is_active=True,
                password_changed_at=now,
                password_expires_at=now + timedelta(days=90),
            )

            db.add(user)

        seed_service_api_keys(db, require_env=require_service_keys)
        db.commit()

        print("Database seeded successfully.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    import sys
    from pathlib import Path

    _platform_dir = Path(__file__).resolve().parent.parent
    if str(_platform_dir) not in sys.path:
        sys.path.insert(0, str(_platform_dir))

    from scripts.migrate_add_user_uuid import run_migration

    Base.metadata.create_all(bind=engine)
    run_migration(engine)
    require_service_keys = "--require-service-keys" in sys.argv

    if "--roles-only" in sys.argv:
        db = SessionLocal()
        try:
            seed_roles(db)
            db.commit()
            print("Roles seeded.")
        finally:
            db.close()
    else:
        seed_database(require_service_keys=require_service_keys)
