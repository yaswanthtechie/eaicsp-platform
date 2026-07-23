import asyncio
import httpx
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from app.core.config import settings
from tenacity import retry, stop_after_attempt, retry_if_exception_type

# Shared HTTP client for connection pooling
client = httpx.AsyncClient(timeout=settings.TIMEOUT_SECONDS)

def get_service_name(prefix: str) -> str:
    """Extracts human-readable service name from the route prefix."""
    # e.g. "/api/v1/inventory" -> "Inventory"
    return prefix.strip("/").split("/")[-1].replace("-", " ").capitalize()

# Retry exactly 2 times (3 attempts total: 1 initial + 2 retries)
@retry(
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((
        httpx.ConnectError, 
        httpx.ConnectTimeout, 
        httpx.ReadTimeout, 
        httpx.WriteTimeout, 
        httpx.PoolTimeout
    )),
    reraise=True
)
async def execute_proxy_request(req: httpx.Request) -> httpx.Response:
    """Helper to execute the httpx request with retries."""
    return await client.send(req, stream=True)

class ProxyService:
    @staticmethod
    async def forward_request(request: Request, path: str):
        # Determine the target service URL and Name
        target_base_url = None
        service_name = "Unknown"
        for route_prefix, service_url in settings.SERVICE_ROUTES.items():
            if request.url.path.startswith(route_prefix):
                target_base_url = service_url
                service_name = get_service_name(route_prefix)
                break
        
        if not target_base_url:
            raise HTTPException(status_code=404, detail="Service not found for the requested path.")
        
        # Append the full original path to the base url
        target_url = httpx.URL(
            f"{target_base_url}{request.url.path}",
            query=request.url.query.encode("utf-8")
        )
        
        # Prepare headers
        headers = dict(request.headers)
        # Remove hop-by-hop headers and let httpx manage the host header
        headers.pop("host", None)
        
        # Build the proxy request
        req = client.build_request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=request.stream()
        )
        
        # Forward the request with retries and timeout handling
        try:
            response = await execute_proxy_request(req)
        except httpx.TimeoutException:
            return JSONResponse(
                status_code=504,
                content={"error": f"{service_name} service timeout"}
            )
        except httpx.RequestError:
            return JSONResponse(
                status_code=503,
                content={"error": f"{service_name} service unavailable"}
            )

        # Stream the response back to the client
        async def stream_response():
            async for chunk in response.aiter_bytes():
                yield chunk
            await response.aclose()
            
        # Copy response headers
        response_headers = dict(response.headers)
        
        # Remove headers that FastAPI/uvicorn will handle automatically for the chunked/streaming response
        response_headers.pop("content-encoding", None)
        response_headers.pop("content-length", None)
        response_headers.pop("transfer-encoding", None)

        return StreamingResponse(
            stream_response(),
            status_code=response.status_code,
            headers=response_headers,
            media_type=response.headers.get("content-type")
        )
