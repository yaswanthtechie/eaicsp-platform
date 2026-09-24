"""
Authentication pre-check service for the API Gateway.

Validates incoming JWT access tokens against Platform Service (/api/v1/auth/verify)
before forwarding traffic to downstream microservices.
"""

import logging
from typing import Any

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, Response

from app.core.config import settings

logger = logging.getLogger("api_gateway.auth_precheck")

# Routes that must never undergo authentication pre-check
EXEMPT_ROUTE_PREFIXES = (
    "/health",
    "/api/v1/auth",
    "/gateway",
)

EXEMPT_EXACT_PATHS = (
    "/",
    "/api/v1/openapi.json",
    "/docs",
    "/redoc",
)


class AuthPrecheckService:
    """
    Gateway-level authentication pre-check service.
    Acts as a security checkpoint for protected downstream routes using
    Platform Service's authoritative /api/v1/auth/verify endpoint.
    """

    @staticmethod
    def is_exempt(path: str) -> bool:
        """
        Check if a given path is exempt from authentication pre-check.
        """
        normalized = (path or "").split("?")[0].rstrip("/") or "/"

        if normalized in EXEMPT_EXACT_PATHS:
            return True

        for prefix in EXEMPT_ROUTE_PREFIXES:
            if normalized == prefix or normalized.startswith(f"{prefix}/"):
                return True

        return False

    @staticmethod
    async def verify_request(
        request: Request,
        route_prefix: str,
        client: httpx.AsyncClient | None = None,
    ) -> Response | None:
        """
        Perform gateway-level authentication pre-check for a protected route.

        Returns:
            - None: Pre-check passed (or disabled / exempt); request should continue.
            - JSONResponse: Pre-check failed; returns immediate error response to client.
        """
        # 1. Check if pre-check is enabled and path is not exempt
        if not getattr(settings, "AUTH_PRECHECK_ENABLED", False):
            return None

        path = request.url.path
        if AuthPrecheckService.is_exempt(path) or AuthPrecheckService.is_exempt(route_prefix):
            return None

        # 2. Extract Authorization header
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")

        if not auth_header:
            logger.info("Auth pre-check rejected: Missing Authorization header on %s", path)
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated"},
            )

        # 3. Check for Bearer token scheme
        parts = auth_header.strip().split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
            logger.info("Auth pre-check rejected: Malformed Authorization header on %s", path)
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
            )

        token = parts[1].strip()

        # 4. Resolve shared or dedicated HTTP client
        http_client: httpx.AsyncClient
        if client is not None:
            http_client = client
        else:
            try:
                http_client = request.app.state.http_client
            except AttributeError:
                http_client = httpx.AsyncClient(timeout=settings.AUTH_PRECHECK_TIMEOUT_SECONDS)

        # 5. Build authoritative verification request directly to Platform Service port
        verify_url = f"{settings.PLATFORM_SERVICE_URL.rstrip('/')}/api/v1/auth/verify"
        request_id = getattr(request.state, "request_id", None) or request.headers.get("x-request-id")

        verify_headers: dict[str, str] = {
            "Authorization": f"Bearer {token}",
            "x-caller-service": "api-gateway",
        }
        if request_id:
            verify_headers["x-request-id"] = request_id

        service_api_key = getattr(settings, "API_GATEWAY_SERVICE_API_KEY", None)
        if service_api_key:
            verify_headers["x-api-key"] = service_api_key
            verify_headers["x-service-name"] = "api_gateway"

        # 6. Dispatch authoritative verification call to Platform Service
        try:
            verify_resp = await http_client.post(
                verify_url,
                headers=verify_headers,
                timeout=settings.AUTH_PRECHECK_TIMEOUT_SECONDS,
            )

            if verify_resp.status_code == 200:
                # Token verified by Platform Service
                logger.debug("Auth pre-check passed for %s", path)
                return None

            if verify_resp.status_code == 401:
                # Platform rejected the token
                try:
                    error_data = verify_resp.json()
                except Exception:
                    error_data = {"detail": "Invalid or expired token"}

                logger.info("Auth pre-check rejected by Platform (401) for %s: %s", path, error_data)
                return JSONResponse(
                    status_code=401,
                    content=error_data,
                )

            # Platform returned 5xx or unexpected error status
            logger.warning(
                "Platform verification returned status %s for %s",
                verify_resp.status_code,
                path,
            )
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Authentication service unavailable",
                    "error": "Platform authentication service error",
                },
            )

        except httpx.TimeoutException:
            logger.warning("Auth pre-check timed out calling Platform /verify for %s", path)
            return JSONResponse(
                status_code=504,
                content={
                    "detail": "Authentication service timeout",
                    "error": "Auth service timeout",
                },
            )

        except httpx.RequestError as exc:
            logger.warning("Auth pre-check connection error calling Platform /verify for %s: %s", path, exc)
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Authentication service unavailable",
                    "error": "Auth service unavailable",
                },
            )


# Global singleton instance
auth_precheck_service = AuthPrecheckService()
