
import httpx


# ============================================================
# AUDIT SUMMARY AUTH TESTS
# ============================================================


def test_audit_summary_without_token_returns_401(client):
    response = client.get(
        "/api/v1/compliance/audit/summary"
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Missing authentication token"
    )


def test_audit_summary_with_invalid_token_returns_401(
    client,
):
    response = client.get(
        "/api/v1/compliance/audit/summary",
        headers={
            "Authorization": "Bearer invalid-token"
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid or expired authentication token"
    )


def test_audit_summary_with_compliance_officer_returns_200(
    client,
    monkeypatch,
):
    class MockResponse:
        status_code = 200

        def json(self):
            return {
                "valid": True,
                "user_id": 1,
                "email": "compliance@company.com",
                "role": "compliance_officer",
                "is_active": True,
            }

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ):
            pass

        async def post(self, *args, **kwargs):
            return MockResponse()

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        MockAsyncClient,
    )

    response = client.get(
        "/api/v1/compliance/audit/summary",
        headers={
            "Authorization": "Bearer valid-token"
        },
    )

    assert response.status_code == 200


def test_audit_summary_wrong_role_returns_403(
    client,
    monkeypatch,
):
    class MockResponse:
        status_code = 200

        def json(self):
            return {
                "valid": True,
                "user_id": 2,
                "email": "user@company.com",
                "role": "procurement_manager",
                "is_active": True,
            }

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ):
            pass

        async def post(self, *args, **kwargs):
            return MockResponse()

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        MockAsyncClient,
    )

    response = client.get(
        "/api/v1/compliance/audit/summary",
        headers={
            "Authorization": "Bearer valid-token"
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Role 'procurement_manager' "
        "is not authorized for this endpoint"
    )


# ============================================================
# POST /OVERRIDE AUTH TESTS
# ============================================================


def test_override_without_token_returns_401(client):
    response = client.post(
        "/api/v1/compliance/override",
        json={
            "entity_name": "Test Entity",
            "matched_name": "TEST ENTITY LTD",
            "source": "OFAC",
            "reason": "Test reason",
            "reviewed_by": "Compliance Officer",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Missing authentication token"
    )


def test_override_with_invalid_token_returns_401(
    client,
):
    response = client.post(
        "/api/v1/compliance/override",
        headers={
            "Authorization": "Bearer invalid-token"
        },
        json={
            "entity_name": "Test Entity",
            "matched_name": "TEST ENTITY LTD",
            "source": "OFAC",
            "reason": "Test reason",
            "reviewed_by": "Compliance Officer",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid or expired authentication token"
    )


def test_override_with_compliance_officer_returns_success(
    client,
    monkeypatch,
):
    class MockResponse:
        status_code = 200

        def json(self):
            return {
                "valid": True,
                "user_id": 1,
                "email": "compliance@company.com",
                "role": "compliance_officer",
                "is_active": True,
            }

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ):
            pass

        async def post(self, *args, **kwargs):
            return MockResponse()

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        MockAsyncClient,
    )

    response = client.post(
        "/api/v1/compliance/override",
        headers={
            "Authorization": "Bearer valid-token"
        },
        json={
            "entity_name": "Test Entity",
            "matched_name": "TEST ENTITY LTD",
            "source": "OFAC",
            "reason": "Confirmed as a false positive",
            "reviewed_by": "Compliance Officer",
        },
    )

    assert response.status_code in (200, 201)


def test_override_wrong_role_returns_403(
    client,
    monkeypatch,
):
    class MockResponse:
        status_code = 200

        def json(self):
            return {
                "valid": True,
                "user_id": 2,
                "email": "user@company.com",
                "role": "procurement_manager",
                "is_active": True,
            }

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ):
            pass

        async def post(self, *args, **kwargs):
            return MockResponse()

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        MockAsyncClient,
    )

    response = client.post(
        "/api/v1/compliance/override",
        headers={
            "Authorization": "Bearer valid-token"
        },
        json={
            "entity_name": "Test Entity",
            "matched_name": "TEST ENTITY LTD",
            "source": "OFAC",
            "reason": "Confirmed as a false positive",
            "reviewed_by": "Compliance Officer",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Role 'procurement_manager' "
        "is not authorized for this endpoint"
    )


# ============================================================
# GET /OVERRIDE AUTH TESTS
# ============================================================


def test_read_override_without_token_returns_401(client):
    response = client.get(
        "/api/v1/compliance/override",
        params={
            "entity_name": "Test Entity",
            "matched_name": "TEST ENTITY LTD",
            "source": "OFAC",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Missing authentication token"
    )


def test_read_override_with_invalid_token_returns_401(
    client,
):
    response = client.get(
        "/api/v1/compliance/override",
        params={
            "entity_name": "Test Entity",
            "matched_name": "TEST ENTITY LTD",
            "source": "OFAC",
        },
        headers={
            "Authorization": "Bearer invalid-token"
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid or expired authentication token"
    )


def test_read_override_with_compliance_officer_returns_success(
    client,
    monkeypatch,
):
    class MockResponse:
        status_code = 200

        def json(self):
            return {
                "valid": True,
                "user_id": 1,
                "email": "compliance@company.com",
                "role": "compliance_officer",
                "is_active": True,
            }

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ):
            pass

        async def post(self, *args, **kwargs):
            return MockResponse()

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        MockAsyncClient,
    )

    response = client.get(
        "/api/v1/compliance/override",
        params={
            "entity_name": "Test Entity",
            "matched_name": "TEST ENTITY LTD",
            "source": "OFAC",
        },
        headers={
            "Authorization": "Bearer valid-token"
        },
    )

    assert response.status_code in (200, 404)


def test_read_override_wrong_role_returns_403(
    client,
    monkeypatch,
):
    class MockResponse:
        status_code = 200

        def json(self):
            return {
                "valid": True,
                "user_id": 2,
                "email": "user@company.com",
                "role": "procurement_manager",
                "is_active": True,
            }

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ):
            pass

        async def post(self, *args, **kwargs):
            return MockResponse()

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        MockAsyncClient,
    )

    response = client.get(
        "/api/v1/compliance/override",
        params={
            "entity_name": "Test Entity",
            "matched_name": "TEST ENTITY LTD",
            "source": "OFAC",
        },
        headers={
            "Authorization": "Bearer valid-token"
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Role 'procurement_manager' "
        "is not authorized for this endpoint"
    )
