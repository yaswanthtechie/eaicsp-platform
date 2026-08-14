import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db
from app.core.config import settings


TEST_DATABASE_URL = settings.TEST_DATABASE_URL


test_engine = create_engine(
    TEST_DATABASE_URL
)


TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine
)


def override_get_db():

    db = TestingSessionLocal()

    try:
        yield db

    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session")
def client():

    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_database():

    Base.metadata.drop_all(bind=test_engine)

    Base.metadata.create_all(bind=test_engine)

    yield

    Base.metadata.drop_all(bind=test_engine)