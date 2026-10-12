"""
Regression tests for PR feedback item 9: Jaeger URL Privacy.

Proves:
1. Query string values, sensitive tokens, and emails are stripped from http.url span attributes.
2. The URL path and scheme remain intact and available for routing/observability.
3. Both gateway server spans and proxy client spans sanitize http.url.
"""

from unittest.mock import AsyncMock, patch
import httpx
import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.main import app
from app.middleware.ratelimit import limiter
from app.middleware.tracing import sanitize_url_for_tracing, set_tracer_provider, shutdown_tracing
from app.services.circuit_breaker import circuit_breaker_manager
from app.services.metrics import metrics_collector


@pytest.fixture
def memory_tracer():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    set_tracer_provider(provider)
    yield exporter
    shutdown_tracing()


@pytest.fixture(autouse=True)
def reset_state():
    circuit_breaker_manager.reset()
    metrics_collector.reset()
    limiter.enabled = False
    yield
    circuit_breaker_manager.reset()
    metrics_collector.reset()
    limiter.enabled = True


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_sanitize_url_helper():
    """Unit test for sanitize_url_for_tracing helper function."""
    url = "https://example.com/api/v1/auth?token=supersecret123&email=user@test.com"
    clean = sanitize_url_for_tracing(url)
    assert clean == "https://example.com/api/v1/auth"
    assert "token" not in clean
    assert "user@test.com" not in clean
    assert sanitize_url_for_tracing(None) == ""
    assert sanitize_url_for_tracing("") == ""


@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_gateway_and_proxy_spans_strip_sensitive_query(mock_send, client, memory_tracer):
    """
    When requests include sensitive tokens or emails in query parameters,
    the resulting spans must NOT contain them in http.url, but must preserve the path.
    """
    mock_send.return_value = httpx.Response(
        status_code=200,
        content=b'{"items": []}',
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://test"),
    )

    sensitive_token = "SECRET_BEARER_TOKEN_999"
    sensitive_email = "confidential_ceo@enterprise.org"
    sensitive_query = f"?token={sensitive_token}&email={sensitive_email}&action=filter"

    response = client.get(f"/api/v1/inventory/items{sensitive_query}")
    assert response.status_code == 200

    spans = memory_tracer.get_finished_spans()
    assert len(spans) >= 2, "Expected at least server and client spans"

    for span in spans:
        attrs = span.attributes or {}
        if "http.url" in attrs:
            url_val = attrs["http.url"]
            assert sensitive_token not in url_val, (
                f"Sensitive token leaked into span http.url: {url_val}"
            )
            assert sensitive_email not in url_val, (
                f"Sensitive email leaked into span http.url: {url_val}"
            )
            assert "?" not in url_val, (
                f"Query string delimiter found in span http.url: {url_val}"
            )
            assert "/api/v1/inventory/items" in url_val, (
                f"Expected route path missing from http.url: {url_val}"
            )
