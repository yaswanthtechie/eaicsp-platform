"""
WebSocket Authentication and Authorization Service for Realtime KPI Feed (R15-M3).

Validates access tokens against the authoritative Platform Service (/api/v1/auth/verify),
enforces the M1 RBAC role allowlist, and handles contract-specified WebSocket close codes.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Set, Tuple

import httpx
from fastapi import WebSocket

from app.core.config import settings

logger = logging.getLogger("api_gateway.realtime.auth")

# Authoritative RBAC role allowlist per M1 contract Section 2.2
ALLOWED_REALTIME_ROLES: Set[str] = {
    "ceo",
    "vp_operations",
    "platform_admin",
    "procurement_manager",
    "logistics_manager",
    "warehouse_manager",
    "inventory_planner",
    "demand_planner",
    "analyst",
    "risk_analyst",
}

# Contract close codes
CLOSE_UNAUTHORIZED = 4401  # Missing, invalid, or expired token
CLOSE_FORBIDDEN = 4403     # Authenticated user lacks allowed role
CLOSE_TRY_AGAIN_LATER = 1013  # Platform /verify unreachable or timed out


class WebSocketAuthService:
    """
    Enforces authentication and authorization for the realtime WebSocket endpoint.
    """

    @staticmethod
    def extract_token(websocket: WebSocket) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract token and negotiated subprotocol from query parameter or Sec-WebSocket-Protocol.

        Returns:
            (token, negotiated_subprotocol)
        """
        # 1. Query parameter token (e.g. ?token=<JWT>)
        token = websocket.query_params.get("token")
        if token and token.strip():
            # If query token is used, subprotocol might be absent or 'bearer'
            return token.strip(), None

        # 2. WebSocket Subprotocol Header (Sec-WebSocket-Protocol: bearer, <JWT>)
        protocol_header = websocket.headers.get("sec-websocket-protocol")
        if protocol_header:
            parts = [p.strip() for p in protocol_header.split(",") if p.strip()]
            if len(parts) >= 2 and parts[0].lower() == "bearer":
                return parts[1], "bearer"
            elif len(parts) == 1 and parts[0].lower() != "bearer":
                # Single non-bearer token format
                return parts[0], None

        return None, None

    @staticmethod
    async def authenticate(
        websocket: WebSocket,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Tuple[bool, Optional[int], Optional[str], Optional[Dict[str, Any]], Optional[str]]:
        """
        Authenticate and authorize the WebSocket connection against Platform /verify.

        Returns:
            (is_authorized, close_code, close_reason, user_data, negotiated_subprotocol)
        """
        token, subprotocol = WebSocketAuthService.extract_token(websocket)

        if not token:
            logger.info("WebSocket auth rejected: missing authentication token")
            return False, CLOSE_UNAUTHORIZED, "Missing authentication token", None, subprotocol

        http_client = client
        if http_client is None:
            try:
                http_client = websocket.app.state.http_client
            except AttributeError:
                http_client = httpx.AsyncClient(timeout=settings.REALTIME_AUTH_TIMEOUT_SECONDS)

        verify_url = f"{settings.PLATFORM_SERVICE_URL.rstrip('/')}/api/v1/auth/verify"
        verify_headers = {
            "Authorization": f"Bearer {token}",
            "x-caller-service": "api-gateway",
        }
        service_api_key = getattr(settings, "API_GATEWAY_SERVICE_API_KEY", None)
        if service_api_key:
            verify_headers["x-api-key"] = service_api_key
            verify_headers["x-service-name"] = "api_gateway"

        timeout = getattr(settings, "REALTIME_AUTH_TIMEOUT_SECONDS", 2.0)

        try:
            resp = await http_client.post(
                verify_url,
                headers=verify_headers,
                timeout=timeout,
            )

            if resp.status_code == 200:
                user_data = resp.json()
                is_active = user_data.get("is_active", True)
                if not is_active:
                    logger.info("WebSocket auth rejected: user is inactive")
                    return False, CLOSE_UNAUTHORIZED, "User account is inactive", user_data, subprotocol

                role = str(user_data.get("role", "")).strip().lower()
                if role not in ALLOWED_REALTIME_ROLES:
                    logger.info("WebSocket auth rejected: role '%s' not in allowlist", role)
                    return False, CLOSE_FORBIDDEN, f"Role '{role}' is not authorized for realtime feed", user_data, subprotocol

                logger.debug("WebSocket client authenticated with role=%s", role)
                return True, None, None, user_data, subprotocol

            elif resp.status_code == 401:
                logger.info("WebSocket auth rejected by Platform: 401 Unauthorized")
                return False, CLOSE_UNAUTHORIZED, "Invalid or expired authentication token", None, subprotocol

            else:
                logger.warning(
                    "Platform /verify returned status %d for WebSocket handshake",
                    resp.status_code,
                )
                return False, CLOSE_TRY_AGAIN_LATER, "Authentication service error", None, subprotocol

        except httpx.TimeoutException:
            logger.warning("Platform /verify timed out (>%.1fs) during WebSocket handshake", timeout)
            return False, CLOSE_TRY_AGAIN_LATER, "Authentication service timeout", None, subprotocol

        except httpx.RequestError as exc:
            logger.warning("Platform /verify connection error during WebSocket handshake: %s", exc)
            return False, CLOSE_TRY_AGAIN_LATER, "Authentication service unavailable", None, subprotocol


ws_auth_service = WebSocketAuthService()
