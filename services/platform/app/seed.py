from app.database import SessionLocal
from app.models.users import User
from app.models.roles import Role
from app.core.security import hash_password
from app.database import Base, engine

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

USERS = [
    {
        "email": "ceo@company.com",
        "full_name": "Company CEO",
        "password": "ceocompany@123",
        "role": "ceo",
    },
    {
        "email": "warehousemanager@company.com",
        "full_name": "Warehouse Manager",
        "password": "warehouse@123",
        "role": "warehouse_manager",
    },
    {
        "email": "vpoperations@company.com",
        "full_name": "VP Operations Manager",
        "password": "vpoperations@123",
        "role": "vp_operations",
    },
    {
        "email": "procurementmanager@company.com",
        "full_name": "Procurement Manager",
        "password": "procurement@123",
        "role": "procurement_manager",
    },
    {
        "email": "logisticsmanager@company.com",
        "full_name": "Logistics Manager",
        "password": "logistics@123",
        "role": "logistics_manager",
    },
    {
        "email": "compliance@company.com",
        "full_name": "Compliance Officer",
        "password": "compliance@123",
        "role": "compliance_officer",
    },
    {
        "email": "analyst@company.com",
        "full_name": "Analyst",
        "password": "analyst@1234",
        "role": "analyst",
    },
    {
        "email": "supplier@company.com",
        "full_name": "Supplier",
        "password": "supplier@123",
        "role": "supplier",
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

        for data in USERS:
            email = data["email"].lower()

            existing_user = (
                db.query(User)
                .filter(User.email == email)
                .first()
            )

            if existing_user:
                continue

            user = User(
                email=email,
                full_name=data["full_name"],
                password=hash_password(data["password"]),
                role_id=role_map[data["role"]].id,
                is_active=True,
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
