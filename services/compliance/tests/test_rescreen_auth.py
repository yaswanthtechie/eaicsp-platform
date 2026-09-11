from unittest.mock import patch

import pytest

from app.services.rescreen_service import (
    authenticate_rescreen_job,
    nightly_rescreen_job,
)


def test_authenticate_rescreen_job_success():
    response_data = {
        "authenticated": True,
        "service": "compliance",
        "auth_type": "api_key",
    }

    with patch(
        "app.services.rescreen_service.httpx.post"
    ) as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = response_data

        result = authenticate_rescreen_job()

    assert result["authenticated"] is True
    assert result["service"] == "compliance"
    assert result["auth_type"] == "api_key"

    mock_post.assert_called_once()

    request = mock_post.call_args

    assert request.kwargs["headers"]["X-API-Key"] != ""

def test_authenticate_rescreen_job_invalid_key():
    with patch(
        "app.services.rescreen_service.httpx.post"
    ) as mock_post:
        mock_post.return_value.status_code = 401

        with pytest.raises(
            RuntimeError,
            match="Platform service authentication failed",
        ):
            authenticate_rescreen_job()

def test_authenticate_rescreen_job_missing_key():
    with patch(
        "app.services.rescreen_service.PLATFORM_SERVICE_API_KEY",
        None,
    ):
        with pytest.raises(
            RuntimeError,
            match="PLATFORM_SERVICE_API_KEY is not configured",
        ):
            authenticate_rescreen_job()

def test_nightly_rescreen_stops_when_authentication_fails():
    with patch(
        "app.services.rescreen_service.authenticate_rescreen_job"
    ) as mock_auth, patch(
        "app.services.rescreen_service.rescreen_cleared_entities"
    ) as mock_rescreen:

        mock_auth.side_effect = RuntimeError(
            "Platform service authentication failed"
        )

        with pytest.raises(
            RuntimeError,
            match="Platform service authentication failed",
        ):
            nightly_rescreen_job()

        mock_rescreen.assert_not_called()