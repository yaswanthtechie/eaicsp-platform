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


def _as_user(role: str):
    """Bypass the real /verify call for tests that are not testing auth."""

    async def _override():
        return {
            "valid": True,
            "role": role,
            "user_id": 1,
        }

    return _override


@pytest.fixture
def client():
    """
    Default client for business-logic tests.

    Uses a warehouse_manager role so authentication does not
    interfere with tests that are not testing authentication.
    """
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_token] = _as_user(
        "warehouse_manager"
    )

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def client_raw():
    """
    Authentication tests.

    Does not override verify_token, so the real Platform Auth
    verification path is executed.
    """
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def client_ceo():
    """Tests that require CEO authorization."""
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_token] = _as_user("ceo")

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def client_warehouse_manager():
    """Tests that specifically require warehouse_manager authorization."""
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_token] = _as_user(
        "warehouse_manager"
    )

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()