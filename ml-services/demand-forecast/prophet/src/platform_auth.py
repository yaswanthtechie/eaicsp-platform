"""Validate forecast API keys against the Platform service."""

import os

import httpx
from fastapi import HTTPException, status


def verify_platform_api_key(api_key: str | None) -> None:
    """Reject missing/invalid keys and fail closed if Platform is unavailable."""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing service API key",
        )

    base_url = os.getenv("PLATFORM_SERVICE_URL", "http://localhost:8005").rstrip("/")

    try:
        response = httpx.post(
            f"{base_url}/api/v1/auth/service-verify",
            headers={"X-API-Key": api_key},
            timeout=3.0,
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Platform authentication service is unavailable",
        ) from exc

    if response.status_code == 401:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service API key",
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Platform authentication service failed",
        )

    try:
        result = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Platform returned an invalid authentication response",
        ) from exc

    if result.get("authenticated") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service API key",
        )
