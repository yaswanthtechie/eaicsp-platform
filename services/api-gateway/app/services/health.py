"""
Health check service for downstream microservices.
"""

import asyncio
import logging

import httpx
from fastapi import Request

from app.core.config import settings
from app.services.proxy import get_service_name

logger = logging.getLogger("api_gateway.health")


async def _ping_service(
    client: httpx.AsyncClient,
    service_name: str,
    base_url: str,
) -> tuple[str, str]:
    """
    Pings a downstream service health endpoint to determine availability.

    Returns:
        (formatted_service_key, "UP" | "DOWN")
    """
    key = service_name.lower().replace(" ", "-")
    try:
        response = await client.get(f"{base_url}/health", timeout=3.0)
        if 200 <= response.status_code < 300:
            return key, "UP"

        logger.warning(
            "Health check for %s (%s/health) returned HTTP status %s",
            service_name,
            base_url,
            response.status_code,
        )
        return key, "DOWN"

    except (httpx.HTTPError, OSError, TimeoutError) as exc:
        logger.warning(
            "Health check for %s (%s/health) failed: %s",
            service_name,
            base_url,
            exc,
        )
        return key, "DOWN"
    except Exception:
        logger.exception(
            "Unexpected error during health check for %s (%s/health)",
            service_name,
            base_url,
        )
        return key, "DOWN"


async def get_system_health(request: Request) -> dict[str, str]:
    """Pings all downstream services asynchronously and returns their health status."""
    try:
        client = request.app.state.http_client
    except AttributeError:
        logger.error("HTTP client is not initialized; cannot perform health checks.")
        return {"error": "health check unavailable"}

    tasks = []
    for prefix, url in settings.SERVICE_ROUTES.items():
        name = get_service_name(prefix)
        tasks.append(_ping_service(client, name, url))

    results = await asyncio.gather(*tasks)
    return {name: status for name, status in results}
