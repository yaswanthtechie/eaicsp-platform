import os

import httpx
import pytest
from sqlalchemy import text

os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://compliance:compliance_dev@localhost:5433/compliance_test"
)
os.environ.setdefault("USE_FIXTURES", "true")

from fastapi.testclient import TestClient

from app.core.database import (
    Base,
    SessionLocal,
    engine,
)
from app.core.dependency import verify_token
from app.main import app
from app.models.audit import ComplianceAudit
from app.models.case_history import CaseHistory
from app.models.compliance_case import ComplianceCase
from app.services import sanctions_service


def clean_test_database(db):
    db.query(CaseHistory).delete()
    db.query(ComplianceCase).delete()
    db.query(ComplianceAudit).delete()

    db.commit()

    db.execute(
        text(
            "SELECT setval("
            "pg_get_serial_sequence('compliance_case', 'id'), "
            "1, false)"
        )
    )
    db.execute(
        text(
            "SELECT setval("
            "pg_get_serial_sequence('case_history', 'id'), "
            "1, false)"
        )
    )
    db.execute(
        text(
            "SELECT setval("
            "pg_get_serial_sequence('compliance_audit', 'id'), "
            "1, false)"
        )
    )

    db.commit()


@pytest.fixture(
    scope="session",
    autouse=True,
)
def create_schema():
    Base.metadata.create_all(
        bind=engine
    )


@pytest.fixture(
    scope="session",
    autouse=True,
)
def load_sanctions(request):
    mark_expression = request.config.getoption("-m")

    if mark_expression.strip() == "integration":
        return

    sanctions_service.load_all_sanctions()


@pytest.fixture(
    autouse=True,
)
def clean_audit_database():
    db = SessionLocal()

    try:
        clean_test_database(db)
        yield
    finally:
        clean_test_database(db)
        db.close()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def mock_compliance_officer_auth():
    async def mock_verify_token():
        return {
            "valid": True,
            "role": "compliance_officer",
            "user_id": 1,
            "email": "test@example.com",
        }

    app.dependency_overrides[
        verify_token
    ] = mock_verify_token

    yield

    app.dependency_overrides.pop(
        verify_token,
        None,
    )


@pytest.fixture
def fake_platform(monkeypatch):
    def _install(
        status_code=200,
        payload=None,
    ):
        if payload is None:
            payload = {
                "valid": True,
                "user_id": 1,
                "email": "compliance@company.com",
                "role": "compliance_officer",
                "is_active": True,
            }

        async def _fake_post(
            self,
            url,
            *args,
            **kwargs,
        ):
            return httpx.Response(
                status_code,
                json=payload,
            )

        monkeypatch.setattr(
            httpx.AsyncClient,
            "post",
            _fake_post,
        )

    return _install

