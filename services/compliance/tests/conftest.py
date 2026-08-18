import pytest

from fastapi.testclient import TestClient

from app.main import app

from app.services import sanctions_service

from app.core.database import (
    SessionLocal,
    Base,
    engine,
)

from app.core.config import (
    OFAC_FIXTURE_PATH,
    UN_FIXTURE_PATH,
    EU_FIXTURE_PATH,
)

from app.models.audit import ComplianceAudit


# ============================================================
# CREATE DATABASE SCHEMA
# ============================================================

@pytest.fixture(
    scope="session",
    autouse=True,
)
def create_schema():
    """
    Create all database tables before the test suite starts.

    This is required because some tests access the database
    without starting the FastAPI application lifespan.
    """

    Base.metadata.create_all(
        bind=engine
    )


# ============================================================
# LOAD LOCAL SANCTIONS FIXTURES
# ============================================================

@pytest.fixture(
    scope="session",
    autouse=True,
)
def load_sanctions():
    """
    Load committed sample sanctions data for unit tests.

    Unit tests use local fixture files instead of downloading
    live OFAC, UN, and EU sanctions data.
    """

    sanctions_service.OFAC_CSV_PATH = (
        OFAC_FIXTURE_PATH
    )

    sanctions_service.UN_XML_PATH = (
        UN_FIXTURE_PATH
    )

    sanctions_service.EU_XML_PATH = (
        EU_FIXTURE_PATH
    )

    sanctions_service.load_all_sanctions()


# ============================================================
# CLEAN AUDIT DATABASE
# ============================================================

@pytest.fixture(
    autouse=True,
)
def clean_audit_database():
    """
    Keep tests isolated from each other.

    The compliance_audit table is cleared before and after
    every test.
    """

    db = SessionLocal()

    try:

        db.query(
            ComplianceAudit
        ).delete()

        db.commit()

        yield

    finally:

        db.query(
            ComplianceAudit
        ).delete()

        db.commit()

        db.close()


# ============================================================
# FASTAPI TEST CLIENT
# ============================================================

@pytest.fixture
def client():

    with TestClient(app) as test_client:

        yield test_client
        