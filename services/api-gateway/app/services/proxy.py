import asyncio
import httpx
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from app.core.config import settings
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential

def get_service_name(prefix: str) -> str:
    """Extracts human-readable service name from the route prefix."""
    return prefix.strip("/").split("/")[-1].replace("-", " ").capitalize()

class ProxyService:
    @staticmethod
    async def forward_request(request: Request, path: str):
        target_base_url = None
        service_name = "Unknown"
        for route_prefix, service_url in settings.SERVICE_ROUTES.items():
            if request.url.path.startswith(route_prefix):
                target_base_url = service_url
                service_name = get_service_name(route_prefix)
                break
        
        if not target_base_url:
            raise HTTPException(status_code=404, detail="Service not found for the requested path.")
        
        target_url = httpx.URL(
            f"{target_base_url}{request.url.path}",
            query=request.url.query.encode("utf-8")
        )
        
        # Read body once to reuse across retries
        body = await request.body()
        
        headers = dict(request.headers)
        hop_by_hop = ["host", "connection", "keep-alive", "transfer-encoding", "upgrade", "content-length"]
        for h in hop_by_hop:
            headers.pop(h, None)
            
        client_ip = request.client.host if request.client else "unknown"
        forwarded_for = headers.get("x-forwarded-for")
        if forwarded_for:
            headers["x-forwarded-for"] = f"{forwarded_for}, {client_ip}"
        else:
            headers["x-forwarded-for"] = client_ip
            
        headers["x-forwarded-proto"] = request.url.scheme
        
        client = request.app.state.http_client

        def is_retryable(retry_state):
            if not retry_state.outcome.failed:
                return False
            exc = retry_state.outcome.exception()
            if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
                return True
            if isinstance(exc, (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout)):
                if request.method in ("GET", "HEAD", "OPTIONS"):
                    return True
            return False

        response = None
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(settings.MAX_RETRIES),
                wait=wait_exponential(multiplier=0.5),
                retry=is_retryable,
                reraise=True
            ):
                with attempt:
                    req = client.build_request(
                        method=request.method,
                        url=target_url,
                        headers=headers,
                        content=body
                    )
                    response = await client.send(req, stream=True)
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

        async def stream_response():
            try:
                async for chunk in response.aiter_bytes():
                    yield chunk
            finally:
                await response.aclose()
            
        response_headers = dict(response.headers)
        response_headers.pop("content-encoding", None)
        response_headers.pop("content-length", None)
        response_headers.pop("transfer-encoding", None)

        return StreamingResponse(
            stream_response(),
            status_code=response.status_code,
            headers=response_headers,
            media_type=response.headers.get("content-type")
        )
