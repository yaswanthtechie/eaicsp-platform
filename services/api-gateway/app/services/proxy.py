"""
HTTP reverse-proxy service used by the API Gateway.
"""
import asyncio
import inspect
import logging
import re
import time
import uuid
from typing import Any

import httpx
import websockets
from fastapi import HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from websockets.exceptions import ConnectionClosed
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.services.auth import auth_precheck_service
from app.services.circuit_breaker import circuit_breaker_manager
from app.services.metrics import metrics_collector
from app.middleware.tracing import (
    extract_trace_context,
    inject_trace_context,
    sanitize_url_for_tracing,
    start_proxy_span,
    StatusCode,
)

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

# Headers the Gateway alone is authoritative for. Whatever the caller sends
# under these names is dropped and replaced, so an external client can never
# forge the identity of an internal service.
GATEWAY_CONTROLLED_HEADERS = {
    "x-caller-service",
    "x-service-name",
    "x-api-key",
    "x-service-api-key",
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
        name = name.removesuffix(" Service")
        return name

    return (
        prefix.strip("/")
        .split("/")[-1]
        .replace("-", " ")
        .capitalize()
    )




def _find_service_route(path: str) -> tuple[str, str] | None:
    """
    Find the most specific downstream route matching the request path.

    Pattern-based overrides in SERVICE_ROUTE_PATTERNS take precedence.
    Otherwise, longer route prefixes take precedence over broader prefixes.
    This prevents nested routes from being matched by a parent route.
    """
    patterns = getattr(settings, "SERVICE_ROUTE_PATTERNS", {})
    for pattern, owner_prefix in patterns.items():
        if re.fullmatch(pattern, path):
            if owner_prefix in settings.SERVICE_ROUTES:
                return owner_prefix, settings.SERVICE_ROUTES[owner_prefix]

    for route_prefix, service_url in sorted(
        settings.SERVICE_ROUTES.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if path == route_prefix or path.startswith(f"{route_prefix}/"):
            return route_prefix, service_url

    return None


def _extract_websocket_token(websocket: WebSocket) -> str | None:
    """
    Extract authentication token from an incoming WebSocket connection.

    Checks in order:
    1. Authorization header using the Bearer scheme.
    2. ?token=<jwt> query parameter.
    3. Sec-WebSocket-Protocol: bearer, <jwt> subprotocol format.

    Returns None when no valid token is found.
    """
    # 1. Authorization header using the Bearer scheme
    auth_header = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
    if auth_header:
        parts = auth_header.strip().split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
            return parts[1].strip()

    # 2. ?token=<jwt> query parameter
    token = websocket.query_params.get("token")
    if token and token.strip():
        return token.strip()

    # 3. Sec-WebSocket-Protocol: bearer, <jwt> subprotocol format
    subprotocols_header = (
        websocket.headers.get("sec-websocket-protocol")
        or websocket.headers.get("Sec-WebSocket-Protocol")
        or ""
    )
    if subprotocols_header:
        subprotocols = [s.strip() for s in subprotocols_header.split(",") if s.strip()]
        for i, sub in enumerate(subprotocols):
            if sub.lower() == "bearer" and i + 1 < len(subprotocols) and subprotocols[i + 1]:
                return subprotocols[i + 1]

    return None


def _safe_websocket_exception_detail(
    exc: Exception,
    target_url: str | None = None,
    query: str | None = None,
    token: str | None = None,
) -> str:
    """
    Ensure WebSocket exception log messages do not expose raw tokens,
    sensitive query parameters, authorization headers, or downstream URLs.
    Returns type(exc).__name__ when sensitive information is detected or suspected,
    otherwise returns a safe string representation.
    """
    exc_str = str(exc)
    if not exc_str:
        return type(exc).__name__

    exc_lower = exc_str.lower()

    if target_url and target_url in exc_str:
        return type(exc).__name__

    if query:
        if query in exc_str:
            return type(exc).__name__
        for part in query.split("&"):
            if part and part in exc_str:
                return type(exc).__name__
            if "=" in part:
                val = part.split("=", 1)[1]
                if val and val in exc_str:
                    return type(exc).__name__

    if token and token in exc_str:
        return type(exc).__name__

    # Check for sensitive indicators/credentials
    sensitive_markers = (
        "token",
        "secret",
        "bearer",
        "key",
        "password",
        "passwd",
        "auth",
        "credential",
        "jwt",
        "signature",
    )
    if any(marker in exc_lower for marker in sensitive_markers):
        return type(exc).__name__

    # Check for presence of URLs with query strings (e.g. ws://...?foo=bar)
    if ("ws://" in exc_str or "wss://" in exc_str or "http://" in exc_str or "https://" in exc_str) and "?" in exc_str:
        return type(exc).__name__

    return exc_str


def build_downstream_url(
    target_base_url: str,
    path: str,
    route_prefix: str,
    query: str = "",
    rewrites: dict[str, str] | None = None,
) -> str:
    """
    Construct the downstream URL applying configured path rewrites
    and preserving query parameters.
    """
    base = target_base_url.rstrip("/")
    path_part = path
    if rewrites is None:
        rewrites = getattr(settings, "SERVICE_ROUTE_REWRITES", {})

    rewrite_prefix = rewrites.get(route_prefix)
    matched_prefix = route_prefix
    if rewrite_prefix is None:
        for key in sorted(rewrites.keys(), key=len, reverse=True):
            if path == key or path.startswith(f"{key}/"):
                rewrite_prefix = rewrites[key]
                matched_prefix = key
                break

    if rewrite_prefix is not None:
        suffix = path[len(matched_prefix):]
        if not suffix.startswith("/") and suffix:
            suffix = "/" + suffix
        path_part = rewrite_prefix.rstrip("/") + suffix
        if not path_part.startswith("/"):
            path_part = "/" + path_part

    if query:
        return f"{base}{path_part}?{query}"
    return f"{base}{path_part}"


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
        and key.lower() not in GATEWAY_CONTROLLED_HEADERS
        and key.lower() != "host"
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

    # Propagate or set X-Request-ID for downstream services
    request_id = getattr(request.state, "request_id", None) or headers.get("x-request-id")
    if request_id:
        headers["x-request-id"] = request_id

    # The Gateway is the authority on caller identity. These are set
    # unconditionally: any client-supplied value was dropped above.
    headers["x-caller-service"] = "api-gateway"

    service_api_key = getattr(settings, "API_GATEWAY_SERVICE_API_KEY", None)
    if service_api_key:
        headers["x-api-key"] = service_api_key
        headers["x-service-name"] = "api_gateway"

    return headers


def _build_response_headers(
    response: Any,
) -> dict[str, str]:
    """
    Copy downstream response headers while removing hop-by-hop
    and streaming-related headers that should be managed by
    StreamingResponse.
    """
    excluded_headers = HOP_BY_HOP_HEADERS | {
        "content-length",
        "content-encoding",
        "date",
        "server",
    }

    raw_headers = getattr(response, "headers", None)
    if raw_headers is not None and hasattr(raw_headers, "items"):
        return {
            key: value
            for key, value in raw_headers.items()
            if key.lower() not in excluded_headers
        }
    return {}


def _safe_status_code(response: Any) -> int:
    """
    Safely extract an integer status code from a real or mocked response.
    Defaults to 200 if status_code is a Mock / non-integer.
    """
    raw_status = getattr(response, "status_code", 200)
    if isinstance(raw_status, int) and not isinstance(raw_status, bool):
        return raw_status
    try:
        return int(raw_status)
    except (TypeError, ValueError):
        return 200


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
        - Authentication pre-check (M5)
        - Circuit breaker checking and recording
        - Metrics collection
        - Request body forwarding
        - Query parameters
        - Header forwarding and sanitization
        - X-Forwarded-* headers
        - OpenTelemetry W3C trace propagation & proxy client span
        - Retry handling with exponential backoff
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
        caller_service = "api-gateway"
        start_time = time.perf_counter()

        # ------------------------------------------------------------------
        # Authentication Pre-Check (M5)
        # ------------------------------------------------------------------
        auth_error = await auth_precheck_service.verify_request(
            request, route_prefix
        )
        if auth_error is not None:
            return auth_error

        # ------------------------------------------------------------------
        # Circuit Breaker Check
        # ------------------------------------------------------------------
        if not circuit_breaker_manager.can_execute(service_id):
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            metrics_collector.record_request(
                service_name=service_id,
                latency_ms=elapsed_ms,
                route=route_prefix,
                status_code=503,
                is_error=True,
                caller_service=caller_service,
            )
            try:
                if hasattr(request, "state"):
                    request.state.metrics_recorded = True
            except Exception:
                pass
            return JSONResponse(
                status_code=503,
                content={
                    "error": f"{service_name} service circuit breaker open"
                },
            )

        # ------------------------------------------------------------------
        # 2. Build downstream URL
        # ------------------------------------------------------------------
        query = str(request.url.query) if request.url.query else ""
        target_url = build_downstream_url(
            target_base_url=target_base_url,
            path=request.url.path,
            route_prefix=route_prefix,
            query=query,
        )


        # ------------------------------------------------------------------
        # 3. Read request body once
        # ------------------------------------------------------------------
        body = await request.body()

        content: bytes | None
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
        if content is not None and "content-length" in headers:
            headers["content-length"] = str(len(content))

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
        # 6. Retry downstream request within proxy span
        # ------------------------------------------------------------------
        retry_condition = retry_if_exception(
            lambda exc: _is_retryable_exception(
                exc,
                request.method,
            )
        )

        response: Any = None

        with start_proxy_span(request.method, service_name, str(target_url)) as proxy_span:
            inject_trace_context(headers)

            try:
                async for attempt in AsyncRetrying(
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
                status_code = _safe_status_code(response)

                metrics_collector.record_request(
                    service_id,
                    elapsed_ms,
                    status_code=status_code,
                    is_error=status_code >= 500,
                    caller_service=caller_service,
                    route=request.url.path,
                )
                try:
                    if hasattr(request, "state"):
                        request.state.metrics_recorded = True
                except Exception:
                    pass

                if status_code >= 500:
                    circuit_breaker_manager.record_failure(service_id)
                elif status_code in {401, 403}:
                    # HTTP 401/403 are client authentication/authorization outcomes,
                    # NOT downstream infrastructure failures. Excluded from breaker statistics
                    # so they neither count as failures nor artificially dilute real 5xx failures.
                    pass
                else:
                    circuit_breaker_manager.record_success(service_id)

                if proxy_span is not None:
                    proxy_span.set_attribute("http.status_code", status_code)
                    if status_code >= 500:
                        proxy_span.set_status(StatusCode.ERROR, f"HTTP {status_code}")
                    else:
                        proxy_span.set_status(StatusCode.OK)

            except httpx.TimeoutException:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                metrics_collector.record_request(
                    service_id,
                    elapsed_ms,
                    is_error=True,
                    status_code=504,
                    caller_service=caller_service,
                    route=request.url.path,
                )
                try:
                    if hasattr(request, "state"):
                        request.state.metrics_recorded = True
                except Exception:
                    pass
                circuit_breaker_manager.record_failure(service_id)
                if proxy_span is not None:
                    proxy_span.set_status(StatusCode.ERROR, f"{service_name} service timeout")
                return JSONResponse(
                    status_code=504,
                    content={
                        "error": f"{service_name} service timeout"
                    },
                )

            except httpx.RequestError:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                metrics_collector.record_request(
                    service_id,
                    elapsed_ms,
                    is_error=True,
                    status_code=503,
                    caller_service=caller_service,
                    route=request.url.path,
                )
                try:
                    if hasattr(request, "state"):
                        request.state.metrics_recorded = True
                except Exception:
                    pass
                circuit_breaker_manager.record_failure(service_id)
                if proxy_span is not None:
                    proxy_span.set_status(StatusCode.ERROR, f"{service_name} service unavailable")
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": f"{service_name} service unavailable"
                    },
                )

            except RuntimeError as exc:
                # Indicates that shared HTTP client has already been closed
                # during application shutdown.
                if "client has been closed" in str(exc).lower():
                    return JSONResponse(
                        status_code=503,
                        content={
                            "error": f"{service_name} service unavailable"
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
                if hasattr(response, "aiter_bytes"):
                    async for chunk in response.aiter_bytes():
                        yield chunk
            finally:
                if hasattr(response, "aclose"):
                    await response.aclose()

        # ------------------------------------------------------------------
        # 9. Prepare response headers
        # ------------------------------------------------------------------
        response_headers = _build_response_headers(response)

        raw_status = getattr(response, "status_code", 200)
        final_status = raw_status if isinstance(raw_status, int) and not isinstance(raw_status, bool) else status_code

        # ------------------------------------------------------------------
        # 10. Return gateway response
        # ------------------------------------------------------------------
        media_type = None
        raw_headers = getattr(response, "headers", None)
        if raw_headers is not None and hasattr(raw_headers, "get"):
            media_type = raw_headers.get("content-type")

        return StreamingResponse(
            content=stream_response(),
            status_code=final_status,
            headers=response_headers,
            media_type=media_type,
        )

    @staticmethod
    async def forward_websocket(
        websocket: WebSocket,
        path: str,
    ) -> None:
        """
        Proxy an incoming WebSocket connection to the configured downstream service.
        Supports bidirectional message streaming, query preservation, and path rewrites.
        """
        normalized_path = "/" + path.lstrip("/")
        route = _find_service_route(normalized_path)
        if route is None or normalized_path not in settings.WEBSOCKET_ROUTE_ALLOWLIST:
            await websocket.close(code=1008, reason="Service not found for the requested path.")
            return

        route_prefix, target_base_url = route

        auth_error = await auth_precheck_service.verify_request(
            websocket,
            route_prefix,
            bearer_token=_extract_websocket_token(websocket),
        )
        if auth_error is not None:
            status_code = getattr(auth_error, "status_code", 401)
            if status_code == 401:
                await websocket.accept()
                await websocket.close(code=4401, reason="Unauthorized")
            else:
                await websocket.accept()
                await websocket.close(code=1013, reason="Try again later")
            return

        # Convert http/https target base URL to ws/wss
        if target_base_url.startswith("https://"):
            ws_base = "wss://" + target_base_url[len("https://"):]
        elif target_base_url.startswith("http://"):
            ws_base = "ws://" + target_base_url[len("http://"):]
        else:
            ws_base = target_base_url

        query = str(websocket.url.query) if websocket.url.query else ""
        target_ws_url = build_downstream_url(
            target_base_url=ws_base,
            path=normalized_path,
            route_prefix=route_prefix,
            query=query,
        )

        # Prepare headers for downstream handshake
        headers: dict[str, str] = {}
        client_ip = websocket.client.host if websocket.client is not None else "unknown"
        headers["x-forwarded-for"] = client_ip
        headers["x-forwarded-proto"] = websocket.url.scheme
        headers["x-caller-service"] = "api-gateway"

        req_id = websocket.headers.get("x-request-id") or str(uuid.uuid4())
        headers["x-request-id"] = req_id

        if "authorization" in websocket.headers:
            headers["authorization"] = websocket.headers["authorization"]

        service_api_key = getattr(settings, "API_GATEWAY_SERVICE_API_KEY", None)
        if service_api_key:
            headers["x-api-key"] = service_api_key
            headers["x-service-name"] = "api_gateway"

        # Extract requested subprotocols
        subprotocols_header = websocket.headers.get("sec-websocket-protocol", "")
        requested_subprotocols = [s.strip() for s in subprotocols_header.split(",") if s.strip()]

        # OpenTelemetry distributed tracing
        parent_ctx = extract_trace_context(dict(websocket.headers))
        service_name = get_service_name(route_prefix)

        with start_proxy_span(
            method="WS",
            service_name=service_name,
            target_url=target_ws_url,
            parent_context=parent_ctx,
        ) as proxy_span:
            inject_trace_context(headers)

            connect_params = inspect.signature(websockets.connect).parameters
            header_param = (
                "additional_headers"
                if "additional_headers" in connect_params
                else "extra_headers"
            )
            connect_kwargs: dict[str, Any] = {
                header_param: headers,
                "open_timeout": settings.WEBSOCKET_OPEN_TIMEOUT_SECONDS,
            }
            if requested_subprotocols:
                connect_kwargs["subprotocols"] = requested_subprotocols

            try:
                async with websockets.connect(
                    target_ws_url,
                    **connect_kwargs,
                ) as downstream_ws:
                    negotiated_subprotocol = getattr(downstream_ws, "subprotocol", None)
                    await websocket.accept(subprotocol=negotiated_subprotocol)

                    async def client_to_downstream():
                        try:
                            while True:
                                message = await websocket.receive()
                                msg_type = message.get("type")
                                if msg_type == "websocket.receive":
                                    if "text" in message and message["text"] is not None:
                                        await downstream_ws.send(message["text"])
                                    elif "bytes" in message and message["bytes"] is not None:
                                        await downstream_ws.send(message["bytes"])
                                elif msg_type == "websocket.disconnect":
                                    break
                        except (WebSocketDisconnect, asyncio.CancelledError):
                            pass
                        except Exception as exc:
                            logger.debug("WebSocket client->downstream exception: %s", type(exc).__name__)

                    async def downstream_to_client():
                        try:
                            async for msg in downstream_ws:
                                if isinstance(msg, str):
                                    await websocket.send_text(msg)
                                elif isinstance(msg, bytes):
                                    await websocket.send_bytes(msg)
                        except (ConnectionClosed, asyncio.CancelledError):
                            pass
                        except Exception as exc:
                            logger.debug("WebSocket downstream->client exception: %s", type(exc).__name__)

                    client_task = asyncio.create_task(client_to_downstream())
                    downstream_task = asyncio.create_task(downstream_to_client())

                    done, pending = await asyncio.wait(
                        [client_task, downstream_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for task in pending:
                        task.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)

            except asyncio.CancelledError:
                pass
            except Exception as exc:
                if proxy_span is not None:
                    proxy_span.record_exception(exc)
                    proxy_span.set_status(StatusCode.ERROR, str(exc))
                # Never log the raw URL: it can carry ?token=<jwt>.
                err_detail = _safe_websocket_exception_detail(
                    exc=exc,
                    target_url=target_ws_url,
                    query=query,
                    token=_extract_websocket_token(websocket),
                )
                logger.warning(
                    "Downstream WebSocket connection failed (%s): %s",
                    sanitize_url_for_tracing(target_ws_url),
                    err_detail,
                )
                try:
                    await websocket.close(code=1011, reason="Downstream service unavailable")
                except Exception:
                    pass
