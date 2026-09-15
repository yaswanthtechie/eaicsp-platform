import pytest

from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials

from app.core import auth


# ============================================================
# TEST DATA
# ============================================================

VALID_SUPPLIER_RESPONSE = {
    "valid": True,
    "user_id": 8,
    "email": "supplier@company.com",
    "full_name": "Supplier User",
    "role": "supplier",
    "supplier_id": "SUP001",
    "is_active": True,
}


VALID_PROCUREMENT_RESPONSE = {
    "valid": True,
    "user_id": 4,
    "email": "procurementmanager@company.com",
    "full_name": "Procurement Manager",
    "role": "procurement_manager",
    "supplier_id": None,
    "is_active": True,
}


# ============================================================
# FAKE PLATFORM RESPONSE
# ============================================================

class FakeResponse:
    """
    Fake httpx response returned by Platform Service.
    """

    def __init__(
        self,
        status_code=200,
        json_data=None,
        json_error=False,
    ):
        self.status_code = status_code
        self._json_data = json_data
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("Invalid JSON")

        return self._json_data


# ============================================================
# FAKE HTTP CLIENT
# ============================================================

class FakeAsyncClient:
    """
    Fake httpx.AsyncClient used to simulate
    Platform Service responses.
    """

    def __init__(
        self,
        response=None,
        exception=None,
        captured_request=None,
    ):
        self.response = response
        self.exception = exception
        self.captured_request = captured_request

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        return False

    async def post(self, url, headers):
        if self.captured_request is not None:
            self.captured_request["url"] = url
            self.captured_request["headers"] = headers

        if self.exception:
            raise self.exception

        return self.response


# ============================================================
# REQUEST HELPER
# ============================================================

def create_request(
    path="/api/v1/purchase-orders/PO1001",
    headers=None,
):
    """
    Create a minimal FastAPI Request for direct
    verify_token() testing.
    """

    if headers is None:
        headers = {}

    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [
            (
                key.lower().encode(),
                value.encode(),
            )
            for key, value in headers.items()
        ],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
        "scheme": "http",
    }

    return Request(scope)


# ============================================================
# FIXTURE
# ============================================================

@pytest.fixture(autouse=True)
def remove_dependency_overrides():
    """
    auth_integration_test.py must test the REAL verify_token()
    implementation.

    Therefore the dependency override from conftest.py
    is temporarily removed.
    """

    from app.main import app

    original_overrides = app.dependency_overrides.copy()

    app.dependency_overrides.clear()

    yield

    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)


# ============================================================
# 1. VALID TOKEN
# ============================================================

@pytest.mark.asyncio
async def test_verify_token_valid_token(monkeypatch):
    """
    Valid token returned by Platform Service
    should authenticate successfully.
    """

    fake_response = FakeResponse(
        status_code=200,
        json_data=VALID_SUPPLIER_RESPONSE,
    )

    captured_request = {}

    def fake_async_client(*args, **kwargs):
        return FakeAsyncClient(
            response=fake_response,
            captured_request=captured_request,
        )

    monkeypatch.setattr(
        auth.httpx,
        "AsyncClient",
        fake_async_client,
    )

    request = create_request(
        headers={
            "Authorization": "Bearer valid-token",
        }
    )

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="valid-token",
    )

    result = await auth.verify_token(
        request=request,
        credentials=credentials,
    )

    assert result == VALID_SUPPLIER_RESPONSE

    assert request.state.user_id == 8
    assert request.state.role == "supplier"
    assert request.state.supplier_id == "SUP001"

    assert captured_request["headers"]["Authorization"] == (
        "Bearer valid-token"
    )

    assert (
        captured_request["headers"]["X-Caller-Service"]
        == "supplier-portal"
    )

    assert (
        captured_request["headers"]["X-Caller-Endpoint"]
        == "/api/v1/purchase-orders/PO1001"
    )

    assert "X-Request-ID" in captured_request["headers"]


# ============================================================
# 2. MISSING TOKEN
# ============================================================

@pytest.mark.asyncio
async def test_verify_token_missing_token():
    """
    Missing Authorization token must return 401.
    """

    request = create_request()

    with pytest.raises(auth.HTTPException) as exc_info:

        await auth.verify_token(
            request=request,
            credentials=None,
        )

    assert exc_info.value.status_code == 401

    assert exc_info.value.detail == (
        "Missing authentication token"
    )


# ============================================================
# 3. INVALID / EXPIRED TOKEN
# ============================================================

@pytest.mark.asyncio
async def test_verify_token_invalid_or_expired_token(monkeypatch):
    """
    Platform Service returning 401 means the token
    is invalid or expired.
    """

    fake_response = FakeResponse(
        status_code=401,
        json_data={
            "detail": "Invalid token",
        },
    )

    def fake_async_client(*args, **kwargs):
        return FakeAsyncClient(
            response=fake_response,
        )

    monkeypatch.setattr(
        auth.httpx,
        "AsyncClient",
        fake_async_client,
    )

    request = create_request()

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="expired-token",
    )

    with pytest.raises(auth.HTTPException) as exc_info:

        await auth.verify_token(
            request=request,
            credentials=credentials,
        )

    assert exc_info.value.status_code == 401

    assert exc_info.value.detail == (
        "Invalid or expired authentication token"
    )


# ============================================================
# 4. PLATFORM SERVICE UNAVAILABLE
# ============================================================

@pytest.mark.asyncio
async def test_verify_token_platform_service_unavailable(
    monkeypatch,
):
    """
    Network failure while contacting Platform Service
    must return 503.
    """

    def fake_async_client(*args, **kwargs):
        return FakeAsyncClient(
            exception=auth.httpx.RequestError(
                "Connection failed"
            ),
        )

    monkeypatch.setattr(
        auth.httpx,
        "AsyncClient",
        fake_async_client,
    )

    request = create_request()

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="valid-token",
    )

    with pytest.raises(auth.HTTPException) as exc_info:

        await auth.verify_token(
            request=request,
            credentials=credentials,
        )

    assert exc_info.value.status_code == 503

    assert exc_info.value.detail == (
        "Authentication service is unavailable"
    )


# ============================================================
# 5. PLATFORM SERVICE TIMEOUT
# ============================================================

@pytest.mark.asyncio
async def test_verify_token_platform_service_timeout(
    monkeypatch,
):
    """
    Platform Service timeout must return 503.
    """

    def fake_async_client(*args, **kwargs):
        return FakeAsyncClient(
            exception=auth.httpx.TimeoutException(
                "Request timed out"
            ),
        )

    monkeypatch.setattr(
        auth.httpx,
        "AsyncClient",
        fake_async_client,
    )

    request = create_request()

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="valid-token",
    )

    with pytest.raises(auth.HTTPException) as exc_info:

        await auth.verify_token(
            request=request,
            credentials=credentials,
        )

    assert exc_info.value.status_code == 503

    assert exc_info.value.detail == (
        "Authentication service timed out"
    )


# ============================================================
# 6. UNEXPECTED PLATFORM STATUS
# ============================================================

@pytest.mark.asyncio
async def test_verify_token_unexpected_platform_status(
    monkeypatch,
):
    """
    Platform Service returning a non-200/non-401 response
    must return 503.
    """

    fake_response = FakeResponse(
        status_code=500,
        json_data={
            "detail": "Internal server error",
        },
    )

    def fake_async_client(*args, **kwargs):
        return FakeAsyncClient(
            response=fake_response,
        )

    monkeypatch.setattr(
        auth.httpx,
        "AsyncClient",
        fake_async_client,
    )

    request = create_request()

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="valid-token",
    )

    with pytest.raises(auth.HTTPException) as exc_info:

        await auth.verify_token(
            request=request,
            credentials=credentials,
        )

    assert exc_info.value.status_code == 503

    assert exc_info.value.detail == (
        "Authentication service returned "
        "an unexpected response"
    )


# ============================================================
# 7. INVALID JSON
# ============================================================

@pytest.mark.asyncio
async def test_verify_token_invalid_json(monkeypatch):
    """
    Platform Service returning invalid JSON
    must return 503.
    """

    fake_response = FakeResponse(
        status_code=200,
        json_error=True,
    )

    def fake_async_client(*args, **kwargs):
        return FakeAsyncClient(
            response=fake_response,
        )

    monkeypatch.setattr(
        auth.httpx,
        "AsyncClient",
        fake_async_client,
    )

    request = create_request()

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="valid-token",
    )

    with pytest.raises(auth.HTTPException) as exc_info:

        await auth.verify_token(
            request=request,
            credentials=credentials,
        )

    assert exc_info.value.status_code == 503

    assert exc_info.value.detail == (
        "Authentication service returned invalid JSON"
    )


# ============================================================
# 8. PLATFORM SAYS TOKEN INVALID
# ============================================================

@pytest.mark.asyncio
async def test_verify_token_platform_returns_valid_false(
    monkeypatch,
):
    """
    Platform Service can return HTTP 200 but valid=False.
    This must still result in 401.
    """

    fake_response = FakeResponse(
        status_code=200,
        json_data={
            "valid": False,
        },
    )

    def fake_async_client(*args, **kwargs):
        return FakeAsyncClient(
            response=fake_response,
        )

    monkeypatch.setattr(
        auth.httpx,
        "AsyncClient",
        fake_async_client,
    )

    request = create_request()

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="invalid-token",
    )

    with pytest.raises(auth.HTTPException) as exc_info:

        await auth.verify_token(
            request=request,
            credentials=credentials,
        )

    assert exc_info.value.status_code == 401

    assert exc_info.value.detail == (
        "Invalid authentication token"
    )


# ============================================================
# 9. MISSING USER ID
# ============================================================

@pytest.mark.asyncio
async def test_verify_token_missing_user_id(monkeypatch):
    """
    Authentication response without user_id
    must return 503.
    """

    fake_response = FakeResponse(
        status_code=200,
        json_data={
            "valid": True,
            "role": "supplier",
            "supplier_id": "SUP001",
        },
    )

    def fake_async_client(*args, **kwargs):
        return FakeAsyncClient(
            response=fake_response,
        )

    monkeypatch.setattr(
        auth.httpx,
        "AsyncClient",
        fake_async_client,
    )

    request = create_request()

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="valid-token",
    )

    with pytest.raises(auth.HTTPException) as exc_info:

        await auth.verify_token(
            request=request,
            credentials=credentials,
        )

    assert exc_info.value.status_code == 503

    assert exc_info.value.detail == (
        "Authentication service did not return "
        "user information"
    )


# ============================================================
# 10. MISSING ROLE
# ============================================================

@pytest.mark.asyncio
async def test_verify_token_missing_role(monkeypatch):
    """
    Authentication response without role
    must return 401.
    """

    fake_response = FakeResponse(
        status_code=200,
        json_data={
            "valid": True,
            "user_id": 8,
            "email": "supplier@company.com",
            "supplier_id": "SUP001",
        },
    )

    def fake_async_client(*args, **kwargs):
        return FakeAsyncClient(
            response=fake_response,
        )

    monkeypatch.setattr(
        auth.httpx,
        "AsyncClient",
        fake_async_client,
    )

    request = create_request()

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="valid-token",
    )

    with pytest.raises(auth.HTTPException) as exc_info:

        await auth.verify_token(
            request=request,
            credentials=credentials,
        )

    assert exc_info.value.status_code == 401

    assert exc_info.value.detail == (
        "User role is not assigned"
    )


# ============================================================
# 11. SUPPLIER INFORMATION IS RETURNED
# ============================================================

@pytest.mark.asyncio
async def test_verify_token_returns_supplier_identity(
    monkeypatch,
):
    """
    Supplier authentication must return supplier_id.
    This is critical for R5 supplier scoping.
    """

    fake_response = FakeResponse(
        status_code=200,
        json_data=VALID_SUPPLIER_RESPONSE,
    )

    def fake_async_client(*args, **kwargs):
        return FakeAsyncClient(
            response=fake_response,
        )

    monkeypatch.setattr(
        auth.httpx,
        "AsyncClient",
        fake_async_client,
    )

    request = create_request()

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="supplier-token",
    )

    result = await auth.verify_token(
        request=request,
        credentials=credentials,
    )

    assert result["role"] == "supplier"
    assert result["supplier_id"] == "SUP001"
    assert result["user_id"] == 8


# ============================================================
# 12. REQUEST ID IS FORWARDED
# ============================================================

@pytest.mark.asyncio
async def test_verify_token_forwards_existing_request_id(
    monkeypatch,
):
    """
    Existing X-Request-ID must be forwarded to Platform Service.
    """

    fake_response = FakeResponse(
        status_code=200,
        json_data=VALID_SUPPLIER_RESPONSE,
    )

    captured_request = {}

    def fake_async_client(*args, **kwargs):
        return FakeAsyncClient(
            response=fake_response,
            captured_request=captured_request,
        )

    monkeypatch.setattr(
        auth.httpx,
        "AsyncClient",
        fake_async_client,
    )

    request = create_request(
        headers={
            "X-Request-ID": "test-request-123",
        }
    )

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="supplier-token",
    )

    result = await auth.verify_token(
        request=request,
        credentials=credentials,
    )

    assert result["valid"] is True

    assert (
        captured_request["headers"]["X-Request-ID"]
        == "test-request-123"
    )

    assert request.state.request_id == "test-request-123"


# ============================================================
# 13. ROLE AUTHORIZATION - ALLOWED ROLE
# ============================================================

@pytest.mark.asyncio
async def test_require_roles_allows_authorized_role():
    """
    Supplier should be allowed when supplier role is required.
    """

    request = create_request()

    role_checker = auth.require_roles("supplier")

    result = await role_checker(
        request=request,
        user=VALID_SUPPLIER_RESPONSE,
    )

    assert result == VALID_SUPPLIER_RESPONSE


# ============================================================
# 14. ROLE AUTHORIZATION - DENIED ROLE
# ============================================================

@pytest.mark.asyncio
async def test_require_roles_rejects_unauthorized_role():
    """
    Supplier should be rejected when procurement_manager
    role is required.
    """

    request = create_request()

    role_checker = auth.require_roles(
        "procurement_manager"
    )

    with pytest.raises(auth.HTTPException) as exc_info:

        await role_checker(
            request=request,
            user=VALID_SUPPLIER_RESPONSE,
        )

    assert exc_info.value.status_code == 403

    assert exc_info.value.detail == (
        "Role 'supplier' is not authorized "
        "for this endpoint"
    )


# ============================================================
# 15. ROLE MISSING
# ============================================================

@pytest.mark.asyncio
async def test_require_roles_missing_role():
    """
    Missing role must return 401.
    """

    request = create_request()

    role_checker = auth.require_roles(
        "procurement_manager"
    )

    user_without_role = {
        "valid": True,
        "user_id": 8,
        "email": "supplier@company.com",
        "supplier_id": "SUP001",
    }

    with pytest.raises(auth.HTTPException) as exc_info:

        await role_checker(
            request=request,
            user=user_without_role,
        )

    assert exc_info.value.status_code == 401

    assert exc_info.value.detail == (
        "User role is not assigned"
    )


# ============================================================
# 16. PROCUREMENT MANAGER AUTHORIZATION
# ============================================================

@pytest.mark.asyncio
async def test_require_roles_allows_procurement_manager():
    """
    Procurement manager should be allowed on
    procurement-only endpoints.
    """

    request = create_request()

    role_checker = auth.require_roles(
        "procurement_manager"
    )

    result = await role_checker(
        request=request,
        user=VALID_PROCUREMENT_RESPONSE,
    )

    assert result == VALID_PROCUREMENT_RESPONSE

# ============================================================
# 17. NON-SUPPLIER USER HAS NO SUPPLIER IDENTITY
# ============================================================

@pytest.mark.asyncio
async def test_verify_token_procurement_manager_has_no_supplier_id(
    monkeypatch,
):
    """
    Procurement manager authentication should not have
    a supplier_id because supplier scoping applies only
    to supplier users.
    """

    fake_response = FakeResponse(
        status_code=200,
        json_data=VALID_PROCUREMENT_RESPONSE,
    )

    def fake_async_client(*args, **kwargs):
        return FakeAsyncClient(
            response=fake_response,
        )

    monkeypatch.setattr(
        auth.httpx,
        "AsyncClient",
        fake_async_client,
    )

    request = create_request()

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="procurement-token",
    )

    result = await auth.verify_token(
        request=request,
        credentials=credentials,
    )

    assert result["valid"] is True
    assert result["role"] == "procurement_manager"
    assert result["user_id"] == 4
    assert result["supplier_id"] is None

# ============================================================
# 18. SUPPLIER WITHOUT SUPPLIER ID
# ============================================================

@pytest.mark.asyncio
async def test_verify_token_supplier_without_supplier_id_is_rejected(
    monkeypatch,
):
    """
    A supplier-role authentication response without supplier_id
    must be rejected at the authentication boundary.
    """

    fake_response = FakeResponse(
        status_code=200,
        json_data={
            "valid": True,
            "user_id": 42,
            "email": "unmapped-supplier@example.com",
            "full_name": "Unmapped Supplier",
            "role": "supplier",
            "is_active": True,
            # supplier_id intentionally omitted
        },
    )

    def fake_async_client(*args, **kwargs):
        return FakeAsyncClient(
            response=fake_response,
        )

    monkeypatch.setattr(
        auth.httpx,
        "AsyncClient",
        fake_async_client,
    )

    request = create_request()

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="supplier-token",
    )

    with pytest.raises(auth.HTTPException) as exc_info:

        await auth.verify_token(
            request=request,
            credentials=credentials,
        )

    assert exc_info.value.status_code == 403

    assert exc_info.value.detail == (
        "Supplier identity could not be resolved"
    )

