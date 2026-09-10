import pytest

from fastapi.testclient import TestClient

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


SUPPLIER_B_USER = {
    "valid": True,
    "user_id": 99,
    "role": "supplier",
    "supplier_id": "SUP002",
    "email": "supplierb@example.com",
    "full_name": "Supplier B",
    "is_active": True,
}


SUPPLIER_NO_ID_USER = {
    "valid": True,
    "user_id": 100,
    "email": "supplier-no-id@example.com",
    "full_name": "Supplier Without ID",
    "role": "supplier",
    "supplier_id": None,
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


class AuthenticatedTestClient(TestClient):
    """
    TestClient that applies its own authentication user
    immediately before every request.

    This prevents different role-specific clients from
    overwriting each other's authentication state.
    """

    def __init__(self, app, user):
        self.test_user = user
        super().__init__(app)

    def request(self, *args, **kwargs):
        async def mock_verify_token():
            return self.test_user

        app.dependency_overrides[verify_token] = (
            mock_verify_token
        )

        return super().request(*args, **kwargs)


@pytest.fixture(autouse=True)
def mock_authentication():
    """
    Default authentication for tests that do not explicitly
    request a role-specific client.

    Default user = SUP001 supplier.
    """

    async def mock_verify_token():
        return SUPPLIER_USER

    app.dependency_overrides[verify_token] = (
        mock_verify_token
    )

    yield

    app.dependency_overrides.pop(
        verify_token,
        None,
    )


@pytest.fixture
def supplier_client():
    """
    TestClient authenticated as supplier SUP001.
    """

    with AuthenticatedTestClient(
        app,
        SUPPLIER_USER,
    ) as test_client:
        yield test_client


@pytest.fixture
def supplier_b_client():
    """
    TestClient authenticated as supplier SUP002.
    """

    with AuthenticatedTestClient(
        app,
        SUPPLIER_B_USER,
    ) as test_client:
        yield test_client


@pytest.fixture
def supplier_no_id_client():
    """
    TestClient authenticated as supplier without supplier_id.
    """

    with AuthenticatedTestClient(
        app,
        SUPPLIER_NO_ID_USER,
    ) as test_client:
        yield test_client


@pytest.fixture
def procurement_client():
    """
    TestClient authenticated as procurement manager.
    """

    with AuthenticatedTestClient(
        app,
        PROCUREMENT_USER,
    ) as test_client:
        yield test_client


@pytest.fixture
def compliance_client():
    """
    TestClient authenticated as compliance officer.
    """

    with AuthenticatedTestClient(
        app,
        COMPLIANCE_USER,
    ) as test_client:
        yield test_client