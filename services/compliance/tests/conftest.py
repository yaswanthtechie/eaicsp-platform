import pytest



from fastapi.testclient import TestClient

from app.main import app
from app.services import sanctions_service

from app.core.database import SessionLocal, Base, engine
from app.models.audit import ComplianceAudit


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


@pytest.fixture
def client():

    with TestClient(app) as test_client:

        yield test_client