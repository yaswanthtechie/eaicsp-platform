"""
Structured JSON logging middleware for the API Gateway.

Emits every gateway access-log event as a single valid JSON line containing:
- @timestamp (UTC ISO-8601 format)
- level (INFO / WARN / ERROR)
- service.name (gateway service identity)
- http.method (GET, POST, etc.)
- route (bounded route template or normalized path)
- http.status_code (final HTTP status code)
- latency_ms (duration in milliseconds)
- request_id (preserved from X-Request-ID or generated)
- trace_id (active OpenTelemetry span trace ID or null)
- client_ip (client IP address)
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.middleware.ratelimit import get_real_ip
from app.services.metrics import normalize_route

# Access logger emitting structured JSON events
logger = logging.getLogger("api_gateway.access")

_FILE_HANDLER_ATTACHED = False


def configure_access_file_handler(logger_instance: logging.Logger) -> None:
    """
    Attach a rotating file handler to write raw JSON log lines to disk so
    Logstash / Filebeat can reliably harvest and ship them to Elasticsearch.
    """
    global _FILE_HANDLER_ATTACHED
    if _FILE_HANDLER_ATTACHED:
        return

    log_path_env = os.getenv("GATEWAY_ACCESS_LOG_PATH")
    if log_path_env:
        log_file = Path(log_path_env)
    else:
        base_dir = Path(__file__).resolve().parent.parent.parent
        log_file = base_dir / "logs" / "access.log"

    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            str(log_file),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger_instance.addHandler(handler)
        _FILE_HANDLER_ATTACHED = True
    except Exception as exc:
        logging.getLogger("api_gateway").warning(
            "Could not initialize access log file handler at %s: %s", log_file, exc
        )


configure_access_file_handler(logger)


def extract_trace_id(request: Request) -> str | None:
    """
    Extract the active OpenTelemetry trace ID as a 32-character hex string.
    Emits null (None) when trace IDs are unavailable or invalid.
    """
    # 1. Check if span is attached to request.state by TracingMiddleware
    span = getattr(getattr(request, "state", None), "otel_span", None)
    if span is not None:
        try:
            span_ctx = span.get_span_context()
            if span_ctx and getattr(span_ctx, "is_valid", False) and span_ctx.trace_id != 0:
                return format(span_ctx.trace_id, "032x")
        except Exception:
            pass

    # 2. Check active OpenTelemetry span from global trace context
    try:
        from opentelemetry import trace
        current_span = trace.get_current_span()
        if current_span is not None:
            span_ctx = current_span.get_span_context()
            if span_ctx and getattr(span_ctx, "is_valid", False) and span_ctx.trace_id != 0:
                return format(span_ctx.trace_id, "032x")
    except Exception:
        pass

    return None


def resolve_bounded_route(request: Request) -> str:
    """
    Resolve bounded route template or normalized path to avoid high-cardinality explosion.
    Never exposes query parameters, passwords, tokens, or raw entity IDs in route keys.
    """
    path = request.url.path
    normalized = normalize_route(path)
    if normalized != "other":
        return normalized

    # Check if a matched FastAPI route object is available on the request scope
    route_obj = request.scope.get("route")
    if route_obj and hasattr(route_obj, "path") and route_obj.path and route_obj.path != "/{path:path}":
        return str(route_obj.path)

    return "other"


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware emitting a structured JSON access log for every incoming request.
    """

    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:
        start_time = time.perf_counter()
        status_code = 500
        response: Response | None = None

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            raise
        finally:
            process_time_ms = (time.perf_counter() - start_time) * 1000.0

            # Preserve or extract request ID
            request_id = getattr(getattr(request, "state", None), "request_id", None)
            if not request_id:
                request_id = request.headers.get("x-request-id")
            if not request_id:
                request_id = str(uuid.uuid4())

            # Correlate response header if response was constructed
            if response is not None:
                response.headers.setdefault("x-request-id", request_id)

            trace_id = extract_trace_id(request)
            route = resolve_bounded_route(request)
            client_ip = get_real_ip(request)

            if status_code >= 500:
                level = "ERROR"
            elif status_code >= 400:
                level = "WARN"
            else:
                level = "INFO"

            # Service name from server-side configuration (do not trust client headers)
            service_name = getattr(settings, "OTEL_SERVICE_NAME", "api-gateway")

            log_entry = {
                "@timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                "level": level,
                "service.name": service_name,
                "http.method": request.method,
                "route": route,
                "http.status_code": status_code,
                "latency_ms": round(process_time_ms, 2),
                "request_id": request_id,
                "trace_id": trace_id,
                "client_ip": client_ip,
            }

            json_line = json.dumps(log_entry, separators=(",", ":"))

            if status_code >= 500:
                logger.error(json_line)
            elif status_code >= 400:
                logger.warning(json_line)
            else:
                logger.info(json_line)

        return response