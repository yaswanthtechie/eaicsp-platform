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