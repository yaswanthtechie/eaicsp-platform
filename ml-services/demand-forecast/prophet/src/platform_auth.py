"""Validate forecast API keys against the Platform service."""

import os

import httpx

from src.errors import ContractError


# Platform service names allowed to call the forecast endpoint (#300).
ALLOWED_CALLERS = frozenset({"inventory"})

PLATFORM_VERIFY_TIMEOUT_SECONDS = 3.0


def verify_platform_api_key(api_key: str | None) -> str:
    """Reject missing/invalid keys and fail closed if Platform is unavailable.

    Returns the authenticated caller's service name.
    """
    if not api_key:
        raise ContractError(401, "UNAUTHORIZED", "Missing service API key")

    # Platform keys are ASCII. Anything else cannot be sent to Platform.
    if not api_key.isascii():
        raise ContractError(401, "UNAUTHORIZED", "Invalid service API key")

    base_url = os.getenv(
        "PLATFORM_SERVICE_URL", "http://localhost:8005"
    ).rstrip("/")

    try:
        response = httpx.post(
            f"{base_url}/api/v1/auth/service-verify",
            headers={"X-API-Key": api_key},
            timeout=PLATFORM_VERIFY_TIMEOUT_SECONDS,
        )
    except httpx.RequestError as exc:
        raise ContractError(
            503,
            "MODEL_UNAVAILABLE",
            "Platform authentication service is unavailable",
        ) from exc

    if response.status_code == 401:
        raise ContractError(401, "UNAUTHORIZED", "Invalid service API key")

    if response.status_code != 200:
        raise ContractError(
            503,
            "MODEL_UNAVAILABLE",
            "Platform authentication service failed",
        )

    try:
        result = response.json()
    except ValueError as exc:
        raise ContractError(
            503,
            "MODEL_UNAVAILABLE",
            "Platform returned an invalid authentication response",
        ) from exc

    if not isinstance(result, dict) or result.get("authenticated") is not True:
        raise ContractError(401, "UNAUTHORIZED", "Invalid service API key")

    # Only Inventory is authorized to call the forecast endpoint.
    caller_service = result.get("service")

    if caller_service not in ALLOWED_CALLERS:
        raise ContractError(
            403,
            "FORBIDDEN",
            "Service is not allowed to call the forecast endpoint",
        )

    return caller_service
