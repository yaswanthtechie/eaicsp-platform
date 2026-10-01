"""
Round 10 Milestone 1 — GET /metrics endpoint.

Returns Prometheus text-format exposition containing all gateway metrics.
Before generating the response the endpoint:
  1. Syncs circuit breaker states and cache hit rates from MetricsCollector
     into the Prometheus Gauges so scrapers always receive up-to-date values.
  2. Calls prometheus_client.generate_latest to produce the standard
     text/plain; version=0.0.4 content.
"""

from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.services.prometheus_metrics import REGISTRY, sync_gauges_from_collector

router = APIRouter(tags=["Observability"])


@router.get(
    "/metrics",
    summary="Prometheus metrics scrape endpoint",
    description=(
        "Returns all API Gateway metrics in Prometheus text exposition format. "
        "Compatible with any Prometheus scraper or Grafana data source."
    ),
    response_class=Response,
    # Exclude from OpenAPI docs to avoid confusion with JSON endpoints.
    include_in_schema=True,
)
async def get_prometheus_metrics() -> Response:
    """
    Prometheus scrape target.

    Syncs Gauge values from the in-memory MetricsCollector immediately before
    generating the exposition so circuit breaker states and cache hit rates are
    always fresh.
    """
    sync_gauges_from_collector()
    data = generate_latest(REGISTRY)
    return Response(
        content=data,
        media_type=CONTENT_TYPE_LATEST,
    )
