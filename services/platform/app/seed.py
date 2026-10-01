from app.database import SessionLocal
from app.models.users import User
from app.models.roles import Role
from app.core.security import hash_password
from app.database import Base, engine
from datetime import datetime, timezone, timedelta
import os

ROLES = [
    ("ceo", "Chief Executive Officer"),
    ("vp_operations", "VP Operations"),
    ("procurement_manager", "Procurement Manager"),
    ("logistics_manager", "Logistics Manager"),
    ("compliance_officer", "Compliance Officer"),
    ("warehouse_manager", "Warehouse Manager"),
    ("analyst", "Analyst"),
    ("supplier", "Supplier"),
]

def _required_password(env_var: str) -> str:
    """
    Read a seed password from the environment.

    Raises at call time (not import time) so that importing this module
    -- as the test suite does -- never requires the full set of seed
    passwords to be present.
    """
    try:
        return os.environ[env_var]
    except KeyError:
        raise RuntimeError(
            f"{env_var} is not set. Seed passwords must be supplied via "
            f"environment variables; see .env.example."
        ) from None


def get_seed_users() -> list[dict]:
    return [
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

    ]

def seed_database():
    db = SessionLocal()

    try:
        # ----------------------------------------
        # Create roles
        # ----------------------------------------

        role_map = {}

        for role_name, description in ROLES:
            role = (
                db.query(Role)
                .filter(Role.name == role_name)
                .first()
            )

            if role is None:
                role = Role(
                    name=role_name,
                    description=description,
                )

                db.add(role)
                db.flush()

            role_map[role_name] = role

        # ----------------------------------------
        # Create users
        # ----------------------------------------

        for data in get_seed_users():
            email = data["email"].lower()

            existing_user = (
                db.query(User)
                .filter(User.email == email)
                .first()
            )

            if existing_user:
                continue
            now = datetime.now(timezone.utc)
            
            user = User(
                email=email,
                full_name=data["full_name"],
                password=hash_password(data["password"]),
                role_id=role_map[data["role"]].id,
                supplier_id=data.get("supplier_id"),
                is_active=True,
                password_changed_at=now,
                password_expires_at=now + timedelta(days=90),
            )

            db.add(user)

        db.commit()

        print("Database seeded successfully.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)

    seed_database()

