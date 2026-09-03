from datetime import date, timedelta

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fastapi.testclient import TestClient

from app.main import app

from app.database import (
    Base,
    get_db,
)

from app.core.auth import verify_token
from app.core.config import settings

from app.models.sales_history import (
    SalesHistory,
)


TEST_DATABASE_URL = (
    settings.TEST_DATABASE_URL
)


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


app.dependency_overrides[
    get_db
] = override_get_db


@pytest.fixture(autouse=True)
def clean_dependency_overrides():
    yield
    app.dependency_overrides.pop(verify_token, None)


@pytest.fixture
def auth_ceo():
    app.dependency_overrides[verify_token] = lambda: {
        "user_id": "test-ceo",
        "username": "ceo_user",
        "role": "ceo",
        "valid": True,
    }
    try:
        yield
    finally:
        app.dependency_overrides.pop(verify_token, None)


@pytest.fixture
def auth_vp_operations():
    app.dependency_overrides[verify_token] = lambda: {
        "user_id": "test-vp-ops",
        "username": "vp_ops_user",
        "role": "vp_operations",
        "valid": True,
    }
    try:
        yield
    finally:
        app.dependency_overrides.pop(verify_token, None)


@pytest.fixture
def auth_warehouse_manager():
    app.dependency_overrides[verify_token] = lambda: {
        "user_id": "test-wh-manager",
        "username": "wh_manager_user",
        "role": "warehouse_manager",
        "valid": True,
    }
    try:
        yield
    finally:
        app.dependency_overrides.pop(verify_token, None)


@pytest.fixture
def auth_procurement_manager():
    app.dependency_overrides[verify_token] = lambda: {
        "user_id": "test-procurement-manager",
        "username": "procurement_manager_user",
        "role": "procurement_manager",
        "valid": True,
    }
    try:
        yield
    finally:
        app.dependency_overrides.pop(verify_token, None)


@pytest.fixture
def client():
    test_client = TestClient(app)
    yield test_client
    test_client.close()

@pytest.fixture(
    autouse=True
)
def reset_database():

    Base.metadata.drop_all(
        bind=test_engine
    )

    Base.metadata.create_all(
        bind=test_engine
    )

    yield

    Base.metadata.drop_all(
        bind=test_engine
    )


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

            sale_date = (
                end_date
                - timedelta(days=i)
            )

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