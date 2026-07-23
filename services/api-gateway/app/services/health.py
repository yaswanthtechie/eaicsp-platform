import asyncio
import httpx
from typing import Dict
from app.core.config import settings
from app.services.proxy import get_service_name

async def _ping_service(client: httpx.AsyncClient, service_name: str, base_url: str) -> tuple[str, str]:
    """Pings a service to determine if it is up or down."""
    try:
        # Pinging the root endpoint of the downstream service for health
        # Alternatively this could be base_url + "/health" if services standardize it.
        response = await client.get(f"{base_url}/health")
        # Consider any successful or expected client-error response as UP (e.g. 401/404 means it's running)
        status = "UP" if response.status_code < 500 else "DOWN"
    except httpx.RequestError:
        status = "DOWN"
        
    # Format the key to lowercase (e.g. "Inventory" -> "inventory")
    return service_name.lower().replace(" ", "-"), status

async def get_system_health() -> Dict[str, str]:
    """Pings all downstream services asynchronously and returns their health status."""
    # Use a tighter timeout specifically for health checks to prevent hanging
    async with httpx.AsyncClient(timeout=3.0) as client:
        tasks = []
        for prefix, url in settings.SERVICE_ROUTES.items():
            name = get_service_name(prefix)
            tasks.append(_ping_service(client, name, url))
        
        results = await asyncio.gather(*tasks)
        return {name: status for name, status in results}
