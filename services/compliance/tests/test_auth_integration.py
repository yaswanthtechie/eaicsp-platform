import httpx
import pytest


class _FakeResponse:
    def __init__(
        self,
        status_code,
        payload=None,
    ):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


@pytest.fixture
def fake_platform(monkeypatch):
    def _install(
        status_code=200,
        payload=None,
        exc=None,
    ):
        async def _fake_post(
            self,
            url,
            **kwargs,
        ):
            if exc:
                raise exc

            return _FakeResponse(
                status_code=status_code,
                payload=payload,
            )

        monkeypatch.setattr(
            httpx.AsyncClient,
            "post",
            _fake_post,
        )

    return _install


def _compliance_officer_response():
    return {
        "valid": True,
        "user_id": 1,
        "email": "compliance@company.com",
        "role": "compliance_officer",
        "is_active": True,
    }


def _wrong_role_response():
    return {
        "valid": True,
        "user_id": 2,
        "email": "user@company.com",
        "role": "procurement_manager",
        "is_active": True,
    }


def _authorization_header():
    return {
        "Authorization": "Bearer valid-token",
    }


def _invalid_authorization_header():
    return {
        "Authorization": "Bearer invalid-token",
    }


def _override_payload():
    return {
        "entity_name": "Test Entity",
        "matched_name": "TEST ENTITY LTD",
        "source": "OFAC",
        "reason": "Confirmed as a false positive",
        "reviewed_by": "Compliance Officer",
    }


# ============================================================
# GET /AUDIT/SUMMARY AUTH TESTS
# ============================================================


def test_audit_summary_without_token_returns_401(client):
    response = client.get(
        "/api/v1/compliance/audit/summary",
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Missing authentication token"
    )


def test_audit_summary_with_invalid_token_returns_401(
    client,
    fake_platform,
):
    fake_platform(
        status_code=401,
    )

    response = client.get(
        "/api/v1/compliance/audit/summary",
        headers=_invalid_authorization_header(),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid or expired authentication token"
    )


def test_audit_summary_with_compliance_officer_returns_200(
    client,
    fake_platform,
):
    fake_platform(
        status_code=200,
        payload=_compliance_officer_response(),
    )

    response = client.get(
        "/api/v1/compliance/audit/summary",
        headers=_authorization_header(),
    )

    assert response.status_code == 200


def test_audit_summary_wrong_role_returns_403(
    client,
    fake_platform,
):
    fake_platform(
        status_code=200,
        payload=_wrong_role_response(),
    )

    response = client.get(
        "/api/v1/compliance/audit/summary",
        headers=_authorization_header(),
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
        json=_override_payload(),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Missing authentication token"
    )


def test_override_with_invalid_token_returns_401(
    client,
    fake_platform,
):
    fake_platform(
        status_code=401,
    )

    response = client.post(
        "/api/v1/compliance/override",
        headers=_invalid_authorization_header(),
        json=_override_payload(),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid or expired authentication token"
    )


def test_override_with_compliance_officer_returns_success(
    client,
    fake_platform,
):
    fake_platform(
        status_code=200,
        payload=_compliance_officer_response(),
    )

    response = client.post(
        "/api/v1/compliance/override",
        headers=_authorization_header(),
        json=_override_payload(),
    )

    assert response.status_code in (200, 201)


def test_override_wrong_role_returns_403(
    client,
    fake_platform,
):
    fake_platform(
        status_code=200,
        payload=_wrong_role_response(),
    )

    response = client.post(
        "/api/v1/compliance/override",
        headers=_authorization_header(),
        json=_override_payload(),
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
    fake_platform,
):
    fake_platform(
        status_code=401,
    )

    response = client.get(
        "/api/v1/compliance/override",
        params={
            "entity_name": "Test Entity",
            "matched_name": "TEST ENTITY LTD",
            "source": "OFAC",
        },
        headers=_invalid_authorization_header(),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid or expired authentication token"
    )


def test_read_override_with_compliance_officer_returns_success(
    client,
    fake_platform,
):
    fake_platform(
        status_code=200,
        payload=_compliance_officer_response(),
    )

    response = client.get(
        "/api/v1/compliance/override",
        params={
            "entity_name": "Test Entity",
            "matched_name": "TEST ENTITY LTD",
            "source": "OFAC",
        },
        headers=_authorization_header(),
    )

    assert response.status_code in (200, 404)


def test_read_override_wrong_role_returns_403(
    client,
    fake_platform,
):
    fake_platform(
        status_code=200,
        payload=_wrong_role_response(),
    )

    response = client.get(
        "/api/v1/compliance/override",
        params={
            "entity_name": "Test Entity",
            "matched_name": "TEST ENTITY LTD",
            "source": "OFAC",
        },
        headers=_authorization_header(),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Role 'procurement_manager' "
        "is not authorized for this endpoint"
    )


# ============================================================
# AUTH SERVICE FAILURE TESTS
# ============================================================


def test_auth_service_timeout_returns_503(
    client,
    fake_platform,
):
    fake_platform(
        exc=httpx.TimeoutException("slow"),
    )

    response = client.get(
        "/api/v1/compliance/audit/summary",
        headers=_authorization_header(),
    )

    assert response.status_code == 503
    assert "timed out" in (
        response.json()["detail"].lower()
    )


def test_auth_service_unavailable_returns_503(
    client,
    fake_platform,
):
    fake_platform(
        exc=httpx.ConnectError("down"),
    )

    response = client.get(
        "/api/v1/compliance/audit/summary",
        headers=_authorization_header(),
    )

    assert response.status_code == 503
    assert "unavailable" in (
        response.json()["detail"].lower()
    )



def test_read_all_overrides_without_token_returns_401(client):
    response = client.get(
        "/api/v1/compliance/overrides",
    )

    assert response.status_code == 401


def test_read_all_overrides_with_invalid_token_returns_401(
    client,
    fake_platform,
):
    fake_platform(status_code=401)

    response = client.get(
        "/api/v1/compliance/overrides",
        headers=_invalid_authorization_header(),
    )

    assert response.status_code == 401


def test_read_all_overrides_with_compliance_officer_returns_200(
    client,
    fake_platform,
):
    fake_platform(
        status_code=200,
        payload=_compliance_officer_response(),
    )

    response = client.get(
        "/api/v1/compliance/overrides",
        headers=_authorization_header(),
    )

    assert response.status_code == 200


def test_read_all_overrides_wrong_role_returns_403(
    client,
    fake_platform,
):
    fake_platform(
        status_code=200,
        payload=_wrong_role_response(),
    )

    response = client.get(
        "/api/v1/compliance/overrides",
        headers=_authorization_header(),
    )

    assert response.status_code == 403


def test_remove_override_without_token_returns_401(client):
    response = client.delete(
        "/api/v1/compliance/override",
        params={
            "entity_name": "Test Entity",
            "matched_name": "TEST ENTITY LTD",
            "source": "OFAC",
        },
    )

    assert response.status_code == 401


def test_remove_override_with_invalid_token_returns_401(
    client,
    fake_platform,
):
    fake_platform(status_code=401)

    response = client.delete(
        "/api/v1/compliance/override",
        params={
            "entity_name": "Test Entity",
            "matched_name": "TEST ENTITY LTD",
            "source": "OFAC",
        },
        headers=_invalid_authorization_header(),
    )

    assert response.status_code == 401


def test_remove_override_with_compliance_officer_returns_success(
    client,
    fake_platform,
):
    fake_platform(
        status_code=200,
        payload=_compliance_officer_response(),
    )

    response = client.delete(
        "/api/v1/compliance/override",
        params={
            "entity_name": "Test Entity",
            "matched_name": "TEST ENTITY LTD",
            "source": "OFAC",
        },
        headers=_authorization_header(),
    )

    assert response.status_code in (200, 404)


def test_remove_override_wrong_role_returns_403(
    client,
    fake_platform,
):
    fake_platform(
        status_code=200,
        payload=_wrong_role_response(),
    )

    response = client.delete(
        "/api/v1/compliance/override",
        params={
            "entity_name": "Test Entity",
            "matched_name": "TEST ENTITY LTD",
            "source": "OFAC",
        },
        headers=_authorization_header(),
    )

    assert response.status_code == 403

# ============================================================
# POST /SCREEN AUTH TESTS
# ============================================================

def test_screen_without_token_returns_401(client):
    response = client.post(
        "/api/v1/compliance/screen",
        json={
            "entity_name": "Test Entity",
            "entity_type": "supplier",
            "country": "US",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Missing authentication token"
    )


def test_screen_with_invalid_token_returns_401(
    client,
    fake_platform,
):
    fake_platform(status_code=401)

    response = client.post(
        "/api/v1/compliance/screen",
        headers=_invalid_authorization_header(),
        json={
            "entity_name": "Test Entity",
            "entity_type": "supplier",
            "country": "US",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid or expired authentication token"
    )


def test_screen_with_compliance_officer_returns_success(
    client,
    fake_platform,
):
    fake_platform(
        status_code=200,
        payload=_compliance_officer_response(),
    )

    response = client.post(
        "/api/v1/compliance/screen",
        headers=_authorization_header(),
        json={
            "entity_name": "Test Entity",
            "entity_type": "supplier",
            "country": "US",
        },
    )

    assert response.status_code == 200


def test_screen_wrong_role_returns_403(
    client,
    fake_platform,
):
    fake_platform(
        status_code=200,
        payload=_wrong_role_response(),
    )

    response = client.post(
        "/api/v1/compliance/screen",
        headers=_authorization_header(),
        json={
            "entity_name": "Test Entity",
            "entity_type": "supplier",
            "country": "US",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Role 'procurement_manager' "
        "is not authorized for this endpoint"
    )


# ============================================================
# POST /SCREEN-BULK AUTH TESTS
# ============================================================

def test_screen_bulk_without_token_returns_401(client):
    response = client.post(
        "/api/v1/compliance/screen-bulk",
        json={
            "entity_names": ["Test Entity", "Another Entity"],
            "entity_type": "supplier",
            "country": "US",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Missing authentication token"
    )


def test_screen_bulk_with_invalid_token_returns_401(
    client,
    fake_platform,
):
    fake_platform(status_code=401)

    response = client.post(
        "/api/v1/compliance/screen-bulk",
        headers=_invalid_authorization_header(),
        json={
            "entity_names": ["Test Entity", "Another Entity"],
            "entity_type": "supplier",
            "country": "US",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid or expired authentication token"
    )


def test_screen_bulk_with_compliance_officer_returns_success(
    client,
    fake_platform,
):
    fake_platform(
        status_code=200,
        payload=_compliance_officer_response(),
    )

    response = client.post(
        "/api/v1/compliance/screen-bulk",
        headers=_authorization_header(),
        json={
            "entity_names": ["Test Entity", "Another Entity"],
            "entity_type": "supplier",
            "country": "US",
        },
    )

    assert response.status_code == 200


def test_screen_bulk_wrong_role_returns_403(
    client,
    fake_platform,
):
    fake_platform(
        status_code=200,
        payload=_wrong_role_response(),
    )

    response = client.post(
        "/api/v1/compliance/screen-bulk",
        headers=_authorization_header(),
        json={
            "entity_names": ["Test Entity", "Another Entity"],
            "entity_type": "supplier",
            "country": "US",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Role 'procurement_manager' "
        "is not authorized for this endpoint"
    )


# ============================================================
# GET /AUDIT AUTH TESTS
# ============================================================

def test_audit_without_token_returns_401(client):
    response = client.get(
        "/api/v1/compliance/audit",
        params={
            "entity_name": "Test Entity",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Missing authentication token"
    )


def test_audit_with_invalid_token_returns_401(
    client,
    fake_platform,
):
    fake_platform(status_code=401)

    response = client.get(
        "/api/v1/compliance/audit",
        params={
            "entity_name": "Test Entity",
        },
        headers=_invalid_authorization_header(),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid or expired authentication token"
    )


def test_audit_with_compliance_officer_returns_success(
    client,
    fake_platform,
):
    fake_platform(
        status_code=200,
        payload=_compliance_officer_response(),
    )

    response = client.get(
        "/api/v1/compliance/audit",
        params={
            "entity_name": "Test Entity",
        },
        headers=_authorization_header(),
    )

    assert response.status_code == 200


def test_audit_wrong_role_returns_403(
    client,
    fake_platform,
):
    fake_platform(
        status_code=200,
        payload=_wrong_role_response(),
    )

    response = client.get(
        "/api/v1/compliance/audit",
        params={
            "entity_name": "Test Entity",
        },
        headers=_authorization_header(),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Role 'procurement_manager' "
        "is not authorized for this endpoint"
    )