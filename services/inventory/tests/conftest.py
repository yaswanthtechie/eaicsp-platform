import os

import pytest

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, engine



# -----------------------------------
# PostgreSQL Test Database
# -----------------------------------

os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://postgres:postgres@localhost:5432/inventory_test"
)



# -----------------------------------
# Test Database Session
# -----------------------------------

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)



# -----------------------------------
# Override FastAPI DB Dependency
# -----------------------------------

from app.database import get_db



def override_get_db():

    db = TestingSessionLocal()

    try:
        yield db

    finally:
        db.close()



app.dependency_overrides[get_db] = override_get_db



# -----------------------------------
# Create Test Client
# -----------------------------------

@pytest.fixture
def client():

    return TestClient(app)



# -----------------------------------
# Reset Database Before Every Test
# -----------------------------------

@pytest.fixture(autouse=True)
def reset_database():

    Base.metadata.drop_all(
        bind=engine
    )


    Base.metadata.create_all(
        bind=engine
    )


    yield


    Base.metadata.drop_all(
        bind=engine
    )