import asyncio
# pyrefly: ignore [missing-import]
import httpx
from typing import Dict
from app.core.config import settings
from app.services.proxy import get_service_name
# pyrefly: ignore [missing-import]
from fastapi import Request

async def _ping_service(client: httpx.AsyncClient, service_name: str, base_url: str) -> tuple[str, str]:
    """Pings a service to determine if it is up or down."""
    try:
        response = await client.get(f"{base_url}/health", timeout=3.0)
        status = "UP" if response.status_code < 500 else "DOWN"
    except Exception:
        status = "DOWN"
        
    return service_name.lower().replace(" ", "-"), status

async def get_system_health(request: Request) -> Dict[str, str]:
    """Pings all downstream services asynchronously and returns their health status."""
    client = request.app.state.http_client
    tasks = []
    for prefix, url in settings.SERVICE_ROUTES.items():
        name = get_service_name(prefix)
        tasks.append(_ping_service(client, name, url))
    
    results = await asyncio.gather(*tasks)
    return {name: status for name, status in results}
