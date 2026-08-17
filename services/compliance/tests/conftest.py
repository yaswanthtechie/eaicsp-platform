import pytest

from fastapi.testclient import TestClient

from app.main import app
from app.services.sanctions_service import load_all_sanctions
from app.core.database import SessionLocal
from app.models.audit import ComplianceAudit


@pytest.fixture(
    scope="session",
    autouse=True,
)
def load_sanctions():
    load_all_sanctions()


@pytest.fixture(autouse=True)
def clean_audit_database():
    db = SessionLocal()

    try:
        db.query(ComplianceAudit).delete()
        db.commit()

        yield

    finally:
        db.query(ComplianceAudit).delete()
        db.commit()
        db.close()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client