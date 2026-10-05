import os
import pytest

from app.middleware import tracing as tracing_module


def pytest_configure(config):
    os.environ.setdefault(
        "SECRET_KEY",
        "test-secret-key-for-jwt-signing-do-not-use-in-production",
    )
    # Prevent locust from monkey-patching socket/threading in pytest runs
    os.environ.setdefault("LOCUST_SKIP_MONKEY_PATCH", "1")


def pytest_collection_modifyitems(config, items):
    """
    Exclude @pytest.mark.integration tests by default unless -m integration is specified.
    """
    markexpr = config.getoption("-m", "")
    if "integration" not in markexpr:
        skip_integration = pytest.mark.skip(
            reason="Integration test requiring external services; run with pytest -m integration"
        )
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)


@pytest.fixture(autouse=True)
def isolate_tracing():
    """
    Ensure every test runs with an isolated in-memory TracerProvider when no
    custom provider is set. This prevents background thread leakage from
    BatchSpanProcessor and connection attempts to unreachable Jaeger endpoints.
    Also ensures clean Prometheus metrics state between test modules.
    """
    try:
        from app.services.prometheus_metrics import reset_prometheus_metrics
        reset_prometheus_metrics()
    except Exception:
        pass

    if tracing_module._tracer_provider is None and not tracing_module._tracing_configured:
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME

        resource = Resource.create({SERVICE_NAME: "api-gateway-test"})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(SimpleSpanProcessor(InMemorySpanExporter()))
        tracing_module.setup_tracing(provider=provider)

    yield

    tracing_module.shutdown_tracing()
    try:
        from app.services.prometheus_metrics import reset_prometheus_metrics
        reset_prometheus_metrics()
    except Exception:
        pass
