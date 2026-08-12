"""
HTTP reverse-proxy service used by the API Gateway.
"""

import logging
import time
from typing import Optional

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.services.circuit_breaker import circuit_breaker_manager
from app.services.metrics import metrics_collector

logger = logging.getLogger("api_gateway.proxy")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}

# Methods that are safe to retry because retrying them should not normally
# create duplicate business operations.
RETRYABLE_METHODS = {
    "GET",
    "HEAD",
    "OPTIONS",
    "PUT",
    "DELETE",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_service_name(prefix: str) -> str:
    """
    Extract a human-readable service name from a route prefix.

    Checks settings.SERVICE_NAMES first for an explicit override.
    Otherwise formats the prefix path gracefully.

    Example:
        /api/v1/supplier-risk -> Supplier risk
    """
    explicit = getattr(settings, "SERVICE_NAMES", {})
    if prefix in explicit:
        name = explicit[prefix]
        if name.endswith(" Service"):
            name = name[:-8]
        return name

    return (
        prefix.strip("/")
        .split("/")[-1]
        .replace("-", " ")
        .capitalize()
    )


def _find_service_route(path: str) -> tuple[str, str] | None:
    """
    Find the downstream service matching the request path.

    A route matches only when:
        /api/v1/inventory
    or:
        /api/v1/inventory/...

    This prevents incorrect matches such as:
        /api/v1/inventory-invalid
    """
    for route_prefix, service_url in settings.SERVICE_ROUTES.items():
        if path == route_prefix or path.startswith(f"{route_prefix}/"):
            return route_prefix, service_url

    return None


def _is_retryable_exception(
    exception: BaseException,
    method: str,
) -> bool:
    """
    Decide whether a downstream exception can safely be retried.

    Connection failures are retried only for idempotent/safe methods.
    Timeout errors are also retried only for those methods.

    POST and PATCH are intentionally excluded to avoid accidental
    duplicate business operations.
    """
    if method.upper() not in RETRYABLE_METHODS:
        return False

    # Include the base TimeoutException to cover httpx's timeout hierarchy
    return isinstance(
        exception,
        (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.PoolTimeout,
            httpx.TimeoutException,
        ),
    )


def _build_forward_headers(
    request: Request,
) -> dict[str, str]:
    """
    Build headers for the downstream service.

    Hop-by-hop headers are removed because they belong to the
    current HTTP connection and should not be forwarded.
    """
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }

    client_ip = (
        request.client.host
        if request.client is not None
        else "unknown"
    )

    existing_forwarded_for = headers.get("x-forwarded-for")

    if existing_forwarded_for:
        headers["x-forwarded-for"] = (
            f"{existing_forwarded_for}, {client_ip}"
        )
    else:
        headers["x-forwarded-for"] = client_ip

    headers["x-forwarded-proto"] = request.url.scheme

    # propagate or set X-Request-ID for downstream services
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        headers["x-request-id"] = request_id

    return headers


def _build_response_headers(
    response: httpx.Response,
) -> dict[str, str]:
    """
    Copy downstream response headers while removing hop-by-hop
    and streaming-related headers that should be managed by
    StreamingResponse.
    """
    excluded_headers = HOP_BY_HOP_HEADERS | {
        "content-length",
        "content-encoding",
    }

    return {
        key: value
        for key, value in response.headers.items()
        if key.lower() not in excluded_headers
    }


# ---------------------------------------------------------------------------
# Proxy Service
# ---------------------------------------------------------------------------

class ProxyService:
    """
    Reverse proxy responsible for forwarding API Gateway requests
    to downstream microservices.
    """

    @staticmethod
    async def forward_request(
        request: Request,
        path: str,
    ):
        """
        Forward the incoming request to the appropriate downstream
        microservice.

        Handles:

        - Service discovery from configured routes
        - Request body forwarding
        - Query parameters
        - Header forwarding
        - X-Forwarded-* headers
        - Retry handling
        - Timeout handling
        - Connection failures
        - Streaming responses
        """

        # ------------------------------------------------------------------
        # 1. Resolve downstream service
        # ------------------------------------------------------------------

        route = _find_service_route(request.url.path)

        if route is None:
            raise HTTPException(
                status_code=404,
                detail="Service not found for the requested path.",
            )

        route_prefix, target_base_url = route
        service_name = get_service_name(route_prefix)
        service_id = route_prefix.strip("/").split("/")[-1]
        start_time = time.perf_counter()

        # ------------------------------------------------------------------
        # Circuit Breaker Check
        # ------------------------------------------------------------------

        if not circuit_breaker_manager.can_execute(service_id):
            return JSONResponse(
                status_code=503,
                content={
                    "error": f"{service_name} service circuit breaker open"
                },
            )

        # ------------------------------------------------------------------
        # 2. Build downstream URL
        # ------------------------------------------------------------------

        # NEW: build the target URL using the original path and query as text
        # preserve request.url.query (already percent-encoded by Starlette/httpx)
        base = target_base_url.rstrip('/')
        path = request.url.path  # already starts with /
        query = str(request.url.query)  # keep as text ('' if none)

        if query:
            target_url = f"{base}{path}?{query}"
        else:
            target_url = f"{base}{path}"

        # ------------------------------------------------------------------
        # 3. Read request body once
        # ------------------------------------------------------------------

        body = await request.body()

        content: Optional[bytes]

        if body:
            content = body
        elif request.method.upper() in {"GET", "HEAD", "OPTIONS"}:
            content = None
        else:
            content = b""

        # ------------------------------------------------------------------
        # 4. Prepare headers
        # ------------------------------------------------------------------

        headers = _build_forward_headers(request)

        # ------------------------------------------------------------------
        # 5. Get shared HTTP client
        # ------------------------------------------------------------------

        try:
            client: httpx.AsyncClient = request.app.state.http_client
        except AttributeError as exc:
            raise HTTPException(
                status_code=500,
                detail="API Gateway HTTP client is not initialized.",
            ) from exc

        # ------------------------------------------------------------------
        # 6. Retry downstream request
        # ------------------------------------------------------------------

        retry_condition = retry_if_exception(
            lambda exc: _is_retryable_exception(
                exc,
                request.method,
            )
        )

        response: Optional[httpx.Response] = None

        try:
            async for attempt in AsyncRetrying(
                # settings.MAX_RETRIES is the NUMBER OF RETRIES (e.g. 2 retries → 3 attempts total)
                stop=stop_after_attempt(max(1, settings.MAX_RETRIES + 1)),
                wait=wait_exponential(
                    multiplier=0.5,
                    min=0.5,
                    max=5,
                ),
                retry=retry_condition,
                reraise=True,
            ):
                with attempt:
                    if (
                        attempt.retry_state.attempt_number > 1
                        and attempt.retry_state.outcome
                    ):
                        exc = attempt.retry_state.outcome.exception()
                        logger.info(
                            "Retry attempt %s for %s due to %s",
                            attempt.retry_state.attempt_number,
                            target_url,
                            exc,
                        )

                    downstream_request = client.build_request(
                        method=request.method,
                        url=target_url,
                        headers=headers,
                        content=content,
                    )

                    response = await client.send(
                        downstream_request,
                        stream=True,
                    )
                    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                    metrics_collector.record_request(service_id, elapsed_ms)

                    if response.status_code >= 500:
                        circuit_breaker_manager.record_failure(service_id)
                    else:
                        circuit_breaker_manager.record_success(service_id)

        except httpx.TimeoutException:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            metrics_collector.record_request(service_id, elapsed_ms)
            circuit_breaker_manager.record_failure(service_id)
            return JSONResponse(
                status_code=504,
                content={
                    "error": f"{service_name} service timeout"
                },
            )

        except httpx.RequestError:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            metrics_collector.record_request(service_id, elapsed_ms)
            circuit_breaker_manager.record_failure(service_id)
            return JSONResponse(
                status_code=503,
                content={
                    "error": f"{service_name} service unavailable"
                },
            )

        except RuntimeError as exc:
            # This normally indicates that the shared HTTP client
            # has already been closed during application shutdown.
            if "client has been closed" in str(exc).lower():
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": (
                            f"{service_name} service unavailable"
                        )
                    },
                )

            raise

        # ------------------------------------------------------------------
        # 7. Defensive check
        # ------------------------------------------------------------------

        if response is None:
            return JSONResponse(
                status_code=503,
                content={
                    "error": f"{service_name} service unavailable"
                },
            )

        # ------------------------------------------------------------------
        # 8. Stream downstream response
        # ------------------------------------------------------------------

        async def stream_response():
            """
            Stream downstream response without loading the complete
            response into gateway memory.
            """
            try:
                async for chunk in response.aiter_bytes():
                    yield chunk
            finally:
                await response.aclose()

        # ------------------------------------------------------------------
        # 9. Prepare response headers
        # ------------------------------------------------------------------

        response_headers = _build_response_headers(response)

        # ------------------------------------------------------------------
        # 10. Return gateway response
        # ------------------------------------------------------------------

        return StreamingResponse(
            content=stream_response(),
            status_code=response.status_code,
            headers=response_headers,
            media_type=response.headers.get("content-type"),
        )