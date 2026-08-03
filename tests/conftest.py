import os
import pytest
from dotenv import load_dotenv

# Tests intentionally require a disposable PostgreSQL database. The autouse
# fixture drops and recreates tables, so never point this at production.
load_dotenv(".env")
test_database_url = os.environ.get("TEST_DATABASE_URL")
if not test_database_url:
    raise RuntimeError(
        "Set TEST_DATABASE_URL to a dedicated PostgreSQL test database before running pytest."
    )
if not test_database_url.startswith("postgresql"):
    raise RuntimeError("TEST_DATABASE_URL must use PostgreSQL, not SQLite.")
os.environ["DATABASE_URL"] = test_database_url

from app.database import Base, engine


@pytest.fixture(autouse=True)
def clean_database():
    """Each test owns a fresh schema in the dedicated test database."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
