from unittest.mock import Mock, patch

import httpx
import pytest
from fastapi import HTTPException

from src.platform_auth import verify_platform_api_key


def test_missing_api_key_returns_401():
    with pytest.raises(HTTPException) as exc:
        verify_platform_api_key(None)

    assert exc.value.status_code == 401


def test_invalid_api_key_returns_401():
    with patch("src.platform_auth.httpx.post") as post:
        post.return_value = Mock(status_code=401)

        with pytest.raises(HTTPException) as exc:
            verify_platform_api_key("bad-key")

    assert exc.value.status_code == 401
    post.assert_called_once()


def test_valid_api_key_is_accepted():
    with patch("src.platform_auth.httpx.post") as post:
        post.return_value = Mock(
            status_code=200,
            json=lambda: {
                "authenticated": True,
                "service": "inventory",
                "auth_type": "api_key",
            },
        )

        caller = verify_platform_api_key("test-key")

    assert caller == "inventory"

    post.assert_called_once_with(
        "http://localhost:8005/api/v1/auth/service-verify",
        headers={"X-API-Key": "test-key"},
        timeout=3.0,
    )


def test_valid_key_from_other_service_returns_403():
    with patch("src.platform_auth.httpx.post") as post:
        post.return_value = Mock(
            status_code=200,
            json=lambda: {
                "authenticated": True,
                "service": "supplier-portal",
                "auth_type": "api_key",
            },
        )

        with pytest.raises(HTTPException) as exc:
            verify_platform_api_key("portal-key")

    assert exc.value.status_code == 403
    assert exc.value.error_code == "FORBIDDEN"


def test_non_ascii_api_key_returns_401_without_calling_platform():
    with patch("src.platform_auth.httpx.post") as post:
        with pytest.raises(HTTPException) as exc:
            verify_platform_api_key("k\xe9y")

    assert exc.value.status_code == 401
    post.assert_not_called()


def test_revoked_api_key_from_platform_returns_401():
    with patch("src.platform_auth.httpx.post") as post:
        post.return_value = Mock(
            status_code=401,
            json=lambda: {
                "detail": "Service API key is inactive or revoked"
            },
        )

        with pytest.raises(HTTPException) as exc:
            verify_platform_api_key("revoked-key")

    assert exc.value.status_code == 401
    post.assert_called_once()


def test_platform_unavailable_returns_503():
    with patch(
        "src.platform_auth.httpx.post",
        side_effect=httpx.ConnectError("Platform offline"),
    ):
        with pytest.raises(HTTPException) as exc:
            verify_platform_api_key("test-key")

    assert exc.value.status_code == 503


def test_unexpected_platform_response_returns_503():
    with patch("src.platform_auth.httpx.post") as post:
        post.return_value = Mock(status_code=500)

        with pytest.raises(HTTPException) as exc:
            verify_platform_api_key("test-key")

    assert exc.value.status_code == 503


def test_platform_response_without_authentication_returns_401():
    with patch("src.platform_auth.httpx.post") as post:
        post.return_value = Mock(
            status_code=200,
            json=lambda: {"authenticated": False},
        )

        with pytest.raises(HTTPException) as exc:
            verify_platform_api_key("test-key")

    assert exc.value.status_code == 401
