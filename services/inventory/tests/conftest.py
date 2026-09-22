from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db
from app.core.config import settings
from app.core.auth import verify_token
from app.models.sales_history import SalesHistory


TEST_DATABASE_URL = settings.TEST_DATABASE_URL

test_engine = create_engine(
    TEST_DATABASE_URL,
    pool_pre_ping=True,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


# ============================================================
# DATABASE FIXTURES
# ============================================================

def override_get_db():
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    yield

    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()


# ============================================================
# SALES HISTORY SEED HELPER
# ============================================================

# IMPORTANT:
# This is a NORMAL FUNCTION.
# Do NOT put @pytest.fixture above it.
def seed_sales_history(
    sku_id: str,
    warehouse_id: str,
    daily_quantity: int = 5,
    days: int = 30,
):
    db = TestingSessionLocal()

    try:
        end_date = date.today()

        for i in range(days):
            sale_date = end_date - timedelta(days=i)

            db.add(
                SalesHistory(
                    sku_id=sku_id,
                    warehouse_id=warehouse_id,
                    sale_date=sale_date,
                    quantity_sold=daily_quantity,
                )
            )

        db.commit()

    finally:
        db.close()


# ============================================================
# TEST PERMISSIONS
# ============================================================

ROLE_PERMISSIONS = {
    "ceo": [
        "inventory:read",
        "inventory:write",
        "compliance:read",
        "compliance:write",
        "supplier:read",
        "supplier:write",
        "logistics:read",
        "logistics:write",
    ],
    "vp_operations": [
        "inventory:read",
        "inventory:write",
        "compliance:read",
        "compliance:write",
        "supplier:read",
        "supplier:write",
        "logistics:read",
        "logistics:write",
    ],
    "procurement_manager": [
        "supplier:read",
        "supplier:write",
    ],
    "logistics_manager": [
        "logistics:read",
        "logistics:write",
    ],
    "compliance_officer": [
        "compliance:read",
        "compliance:write",
    ],
    "warehouse_manager": [
        "inventory:read",
        "inventory:write",
    ],
    "analyst": [
        "inventory:read",
        "compliance:read",
        "supplier:read",
        "logistics:read",
    ],
    "supplier": [
        "supplier:read",
        "supplier:write",
    ],
}


def _as_user(role: str):
    async def _override():
        return {
            "valid": True,
            "role": role,
            "user_id": 1,
            "email": f"{role}@example.com",
            "permissions": ROLE_PERMISSIONS.get(role, []),
        }

    return _override


# ============================================================
# DEFAULT CLIENT
# warehouse_manager
# ============================================================

@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db

    app.dependency_overrides[verify_token] = _as_user(
        "warehouse_manager"
    )

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# ============================================================
# RAW CLIENT
# No authentication override
# ============================================================

@pytest.fixture
def client_raw():
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# ============================================================
# CEO CLIENT
# ============================================================

@pytest.fixture
def client_ceo():
    app.dependency_overrides[get_db] = override_get_db

    app.dependency_overrides[verify_token] = _as_user(
        "ceo"
    )

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# ============================================================
# WAREHOUSE MANAGER CLIENT
# ============================================================

@pytest.fixture
def client_warehouse_manager():
    app.dependency_overrides[get_db] = override_get_db

    app.dependency_overrides[verify_token] = _as_user(
        "warehouse_manager"
    )

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()