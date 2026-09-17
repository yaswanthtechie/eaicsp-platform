"""
BFF Aggregation Service for the API Gateway.

Coordinates parallel fan-out requests to downstream microservices:
- Inventory Service: GET /api/v1/inventory
- Compliance Service: GET /api/v1/compliance/audit/summary
- Logistics (Shipments) Service: GET /api/v1/shipments/

Aggregates responses concurrently with graceful failure handling.
"""

import asyncio
import logging
from typing import Any

import httpx
from fastapi import Request

from app.core.config import settings

logger = logging.getLogger("api_gateway.aggregation")

# Hop-by-hop headers that must not be forwarded downstream
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}


def _build_downstream_headers(request: Request) -> dict[str, str]:
    """
    Build forwarded headers for downstream microservice requests.

    - Strips hop-by-hop headers
    - Preserves Authorization header
    - Propagates X-Request-ID
    - Propagates X-Caller-Service (defaults to 'api-gateway' if absent)
    - Adds configured gateway service authentication (X-API-Key, X-Service-Name)
    - Adds client IP tracking (X-Forwarded-For, X-Forwarded-Proto)
    """
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }

    # Track client IP
    client_ip = (
        request.client.host
        if request.client is not None
        else "unknown"
    )
    existing_forwarded_for = headers.get("x-forwarded-for")
    if existing_forwarded_for:
        headers["x-forwarded-for"] = f"{existing_forwarded_for}, {client_ip}"
    else:
        headers["x-forwarded-for"] = client_ip

    headers["x-forwarded-proto"] = request.url.scheme

    # Forward Authorization header if present
    auth_header = request.headers.get("authorization")
    if auth_header:
        headers["authorization"] = auth_header

    # Propagate or generate X-Request-ID
    request_id = getattr(request.state, "request_id", None) or request.headers.get("x-request-id")
    if request_id:
        headers["x-request-id"] = request_id

    # Propagate or default X-Caller-Service
    caller_service = request.headers.get("x-caller-service")
    if caller_service:
        headers["x-caller-service"] = caller_service
    else:
        headers["x-caller-service"] = "api-gateway"

    # Forward service API key if configured and not already provided
    service_api_key = getattr(settings, "API_GATEWAY_SERVICE_API_KEY", None)
    if (
        service_api_key
        and "x-api-key" not in headers
        and "x-service-api-key" not in headers
    ):
        headers["x-api-key"] = service_api_key
        headers["x-service-name"] = "api_gateway"

    return headers


async def _fetch_single_service(
    client: httpx.AsyncClient,
    service_name: str,
    url: str,
    headers: dict[str, str],
) -> dict[str, Any]:
    """
    Execute a single downstream GET request with error isolation.

    Never raises unhandled exceptions or exposes Python tracebacks.
    """
    try:
        req = client.build_request(
            method="GET",
            url=url,
            headers=headers,
            timeout=settings.TIMEOUT_SECONDS,
        )
        response = await client.send(req)

        if 200 <= response.status_code < 300:
            try:
                data = response.json()
            except Exception:
                data = response.text
            return {
                "status": "ok",
                "data": data,
            }

        logger.warning(
            "Downstream service %s returned error status %s",
            service_name,
            response.status_code,
        )
        return {
            "status": "unavailable",
            "data": None,
            "error": f"{service_name.capitalize()} service returned status {response.status_code}",
        }

    except httpx.TimeoutException:
        logger.warning("Downstream service %s timed out", service_name)
        return {
            "status": "unavailable",
            "data": None,
            "error": f"{service_name.capitalize()} service timeout",
        }
    except httpx.RequestError as exc:
        logger.warning("Downstream service %s request error: %s", service_name, exc)
        return {
            "status": "unavailable",
            "data": None,
            "error": f"{service_name.capitalize()} service unavailable",
        }
    except Exception as exc:
        logger.error("Unexpected error querying %s service: %s", service_name, exc)
        return {
            "status": "unavailable",
            "data": None,
            "error": f"{service_name.capitalize()} service unavailable",
        }


def _normalize_result(service_name: str, result: Any) -> dict[str, Any]:
    """
    Ensure the result from asyncio.gather is a properly formatted dict.
    """
    if isinstance(result, Exception):
        return {
            "status": "unavailable",
            "data": None,
            "error": f"{service_name.capitalize()} service unavailable",
        }
    if isinstance(result, dict) and "status" in result:
        return result
    return {
        "status": "unavailable",
        "data": None,
        "error": f"{service_name.capitalize()} service unavailable",
    }


class AggregationService:
    """
    Service responsible for orchestrating BFF aggregation calls.
    """

    @staticmethod
    async def get_dashboard_summary(request: Request) -> dict[str, Any]:
        """
        Fan out in parallel to Inventory, Compliance, and Logistics services,
        collect responses concurrently, and return the aggregated summary.
        """
        headers = _build_downstream_headers(request)

        inventory_url = f"{settings.INVENTORY_SERVICE_URL.rstrip('/')}/api/v1/inventory"
        compliance_url = f"{settings.COMPLIANCE_SERVICE_URL.rstrip('/')}/api/v1/compliance/audit/summary"
        logistics_url = f"{settings.SHIPMENTS_SERVICE_URL.rstrip('/')}/api/v1/shipments/"

        # Obtain HTTP client from app state or create one if unavailable
        app_state = getattr(getattr(request, "app", None), "state", None)
        shared_client = getattr(app_state, "http_client", None) if app_state else None

        if shared_client is not None:
            results = await asyncio.gather(
                _fetch_single_service(shared_client, "inventory", inventory_url, headers),
                _fetch_single_service(shared_client, "compliance", compliance_url, headers),
                _fetch_single_service(shared_client, "logistics", logistics_url, headers),
                return_exceptions=True,
            )
        else:
            async with httpx.AsyncClient(timeout=settings.TIMEOUT_SECONDS) as fallback_client:
                results = await asyncio.gather(
                    _fetch_single_service(fallback_client, "inventory", inventory_url, headers),
                    _fetch_single_service(fallback_client, "compliance", compliance_url, headers),
                    _fetch_single_service(fallback_client, "logistics", logistics_url, headers),
                    return_exceptions=True,
                )

        inventory_res = _normalize_result("inventory", results[0])
        compliance_res = _normalize_result("compliance", results[1])
        logistics_res = _normalize_result("logistics", results[2])

        all_results = [inventory_res, compliance_res, logistics_res]
        success_count = sum(1 for r in all_results if r.get("status") == "ok")

        if success_count == 3:
            overall_status = "complete"
        elif success_count == 0:
            overall_status = "unavailable"
        else:
            overall_status = "partial"

        return {
            "status": overall_status,
            "inventory": inventory_res,
            "compliance": compliance_res,
            "logistics": logistics_res,
        }
