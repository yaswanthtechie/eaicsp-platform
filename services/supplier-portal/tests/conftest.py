import pytest

from app.main import app
from app.core.auth import verify_token


SUPPLIER_USER = {
    "valid": True,
    "user_id": 8,
    "email": "supplier@company.com",
    "full_name": "Supplier User",
    "role": "supplier",
    "supplier_id": "SUP001",
    "is_active": True,
}


PROCUREMENT_USER = {
    "valid": True,
    "user_id": 4,
    "email": "procurementmanager@company.com",
    "full_name": "Procurement Manager",
    "role": "procurement_manager",
    "supplier_id": None,
    "is_active": True,
}


COMPLIANCE_USER = {
    "valid": True,
    "user_id": 6,
    "email": "compliance@company.com",
    "full_name": "Compliance Officer",
    "role": "compliance_officer",
    "supplier_id": None,
    "is_active": True,
}


@pytest.fixture(autouse=True)
def mock_authentication():
    """
    Automatically authenticate tests as SUP001 supplier.

    This is required because test_invoices.py creates
    TestClient(app) directly instead of using a client fixture.
    """

    async def mock_verify_token():
        return SUPPLIER_USER

    app.dependency_overrides[verify_token] = mock_verify_token

    yield

    app.dependency_overrides.clear()


@pytest.fixture
def supplier_client():
    """
    Authenticated supplier client.
    """

    async def mock_verify_token():
        return SUPPLIER_USER

    app.dependency_overrides[verify_token] = mock_verify_token

    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def procurement_client():
    """
    Authenticated procurement manager client.
    """

    async def mock_verify_token():
        return PROCUREMENT_USER

    app.dependency_overrides[verify_token] = mock_verify_token

    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def compliance_client():
    """
    Authenticated compliance officer client.
    """

    async def mock_verify_token():
        return COMPLIANCE_USER

    app.dependency_overrides[verify_token] = mock_verify_token

    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()