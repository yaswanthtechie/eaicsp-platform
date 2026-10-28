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
                "service": "forecast",
                "auth_type": "api_key",
            },
        )

        verify_platform_api_key("test-key")

    post.assert_called_once_with(
        "http://localhost:8005/api/v1/auth/service-verify",
        headers={"X-API-Key": "test-key"},
        timeout=3.0,
    )


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
