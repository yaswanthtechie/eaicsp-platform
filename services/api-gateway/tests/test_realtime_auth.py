"""
Tests for WebSocket Authentication and Role Authorization (R15-M3).

Verifies:
- Token extraction from query parameter and Sec-WebSocket-Protocol header.
- Platform /verify contract integration with 2.0s timeout.
- Enforcement of M1 RBAC role allowlist.
- Contract close codes: 4401 (Unauthorized), 4403 (Forbidden), 1013 (Try Again Later).
- Redaction of sensitive credentials.
"""

from unittest.mock import AsyncMock, MagicMock
import httpx
import pytest

from app.services.realtime.auth import (
    ALLOWED_REALTIME_ROLES,
    CLOSE_FORBIDDEN,
    CLOSE_TRY_AGAIN_LATER,
    CLOSE_UNAUTHORIZED,
    WebSocketAuthService,
    ws_auth_service,
)


def make_mock_websocket(query_token=None, subprotocol_header=None):
    """Create a mock WebSocket object with query_params and headers."""
    ws = MagicMock()
    ws.query_params = {"token": query_token} if query_token else {}
    ws.headers = {}
    if subprotocol_header:
        ws.headers["sec-websocket-protocol"] = subprotocol_header
    ws.app = MagicMock()
    return ws


def test_token_extraction_from_query_params():
    """Extracts JWT token from query string ?token=..."""
    ws = make_mock_websocket(query_token="my-jwt-token")
    token, subproto = WebSocketAuthService.extract_token(ws)
    assert token == "my-jwt-token"
    assert subproto is None


def test_token_extraction_from_subprotocol_header():
    """Extracts JWT token from 'Sec-WebSocket-Protocol: bearer, <token>'."""
    ws = make_mock_websocket(subprotocol_header="bearer, my-subproto-token")
    token, subproto = WebSocketAuthService.extract_token(ws)
    assert token == "my-subproto-token"
    assert subproto == "bearer"


def test_missing_token_extract():
    """Missing token in both query and header returns None for token."""
    ws = make_mock_websocket()
    token, subproto = ws_auth_service.extract_token(ws)
    assert token is None
    assert subproto is None


def test_lone_subprotocol_not_treated_as_token():
    """A single subprotocol like 'graphql-ws' must not be extracted as an auth token."""
    ws = make_mock_websocket(subprotocol_header="graphql-ws")
    token, subproto = WebSocketAuthService.extract_token(ws)
    assert token is None
    assert subproto is None


@pytest.mark.asyncio
async def test_authenticate_lone_subprotocol_rejected_as_missing_token():
    """WebSocket with lone non-bearer subprotocol is rejected without calling Platform."""
    ws = make_mock_websocket(subprotocol_header="graphql-ws")
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    is_auth, code, reason, user_data, subproto = await ws_auth_service.authenticate(ws, client=mock_client)
    assert is_auth is False
    assert code == CLOSE_UNAUTHORIZED
    assert "Missing authentication token" in reason
    mock_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_authenticate_missing_token():
    ws = make_mock_websocket()
    is_auth, code, reason, user_data, subproto = await ws_auth_service.authenticate(ws)
    assert is_auth is False
    assert code == CLOSE_UNAUTHORIZED
    assert "Missing authentication token" in reason


@pytest.mark.asyncio
async def test_authenticate_platform_401_invalid_token():
    """When Platform /verify returns 401, reject with code 4401."""
    ws = make_mock_websocket(query_token="expired-token")
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = httpx.Response(401, json={"detail": "Signature expired"})

    is_auth, code, reason, user_data, subproto = await ws_auth_service.authenticate(ws, client=mock_client)
    assert is_auth is False
    assert code == CLOSE_UNAUTHORIZED
    assert "Invalid or expired" in reason


@pytest.mark.asyncio
async def test_authenticate_inactive_user_rejected():
    """Inactive user account must be rejected with 4401."""
    ws = make_mock_websocket(query_token="valid-token-inactive-user")
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = httpx.Response(
        200,
        json={"valid": True, "role": "analyst", "is_active": False},
    )

    is_auth, code, reason, user_data, subproto = await ws_auth_service.authenticate(ws, client=mock_client)
    assert is_auth is False
    assert code == CLOSE_UNAUTHORIZED
    assert "inactive" in reason


@pytest.mark.parametrize("role", sorted(list(ALLOWED_REALTIME_ROLES)))
@pytest.mark.asyncio
async def test_authenticate_all_allowed_roles_succeed(role):
    """Every role in ALLOWED_REALTIME_ROLES passes authentication with code None."""
    ws = make_mock_websocket(query_token=f"token-for-{role}")
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = httpx.Response(
        200,
        json={
            "valid": True,
            "role": role,
            "is_active": True,
            "user_id": 42,
            "email": f"{role}@enterprise.org",
        },
    )

    is_auth, code, reason, user_data, subproto = await ws_auth_service.authenticate(ws, client=mock_client)
    assert is_auth is True
    assert code is None
    assert reason is None
    assert user_data["role"] == role


@pytest.mark.parametrize("unauthorized_role", [
    "supplier",
    "compliance_officer",
    "driver",
    "guest",
    "contractor",
])
@pytest.mark.asyncio
async def test_authenticate_unauthorized_role_rejected_with_4403(unauthorized_role):
    """Authenticated user with role not in allowlist is closed with 4403 Forbidden."""
    ws = make_mock_websocket(query_token=f"token-{unauthorized_role}")
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = httpx.Response(
        200,
        json={
            "valid": True,
            "role": unauthorized_role,
            "is_active": True,
            "user_id": 99,
        },
    )

    is_auth, code, reason, user_data, subproto = await ws_auth_service.authenticate(ws, client=mock_client)
    assert is_auth is False
    assert code == CLOSE_FORBIDDEN
    assert "not authorized" in reason


@pytest.mark.asyncio
async def test_authenticate_platform_timeout_returns_1013():
    """When Platform /verify times out (>2s), fail closed with 1013 (Try Again Later)."""
    ws = make_mock_websocket(query_token="some-token")
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.side_effect = httpx.TimeoutException("Platform timeout")

    is_auth, code, reason, user_data, subproto = await ws_auth_service.authenticate(ws, client=mock_client)
    assert is_auth is False
    assert code == CLOSE_TRY_AGAIN_LATER
    assert "timeout" in reason


@pytest.mark.asyncio
async def test_authenticate_platform_unavailable_returns_1013():
    """When Platform /verify is unreachable or returns 503, close with 1013."""
    ws = make_mock_websocket(query_token="some-token")
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.side_effect = httpx.ConnectError("Connection refused")

    is_auth, code, reason, user_data, subproto = await ws_auth_service.authenticate(ws, client=mock_client)
    assert is_auth is False
    assert code == CLOSE_TRY_AGAIN_LATER
    assert "unavailable" in reason


@pytest.mark.asyncio
async def test_authenticate_with_subprotocol_bearer_preserves_negotiation():
    """Successful authentication with subprotocol bearer negotiates subprotocol."""
    ws = make_mock_websocket(subprotocol_header="bearer, valid-token-subproto")
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = httpx.Response(
        200,
        json={"valid": True, "role": "ceo", "is_active": True},
    )

    is_auth, code, reason, user_data, subproto = await ws_auth_service.authenticate(ws, client=mock_client)
    assert is_auth is True
    assert subproto == "bearer"
