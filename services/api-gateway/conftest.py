import os
import tempfile

# Tests must never write into logs/access.log (Filebeat ships that file to Kibana).
os.environ.setdefault(
    "GATEWAY_ACCESS_LOG_PATH",
    os.path.join(tempfile.mkdtemp(prefix="gateway-test-logs-"), "access.log"),
)

# Must happen at IMPORT time, before any `app` import: pytest loads
# tests/conftest.py (which imports app and builds Settings()) before any
# pytest_configure hook runs, so setting these inside the hook is too late
# on a clean clone that has no .env file.
os.environ.setdefault(
    "SECRET_KEY",
    "test-secret-key-for-jwt-signing-do-not-use-in-production",
)
# Prevent locust from monkey-patching socket/threading in pytest runs
os.environ.setdefault("LOCUST_SKIP_MONKEY_PATCH", "1")
os.environ.setdefault("METRICS_BEARER_TOKEN", "test-metrics-bearer-token")

# Prevent OpenTelemetry from attempting network connections to unavailable localhost:4318 during tests
os.environ.setdefault("OTEL_TRACES_EXPORTER", "none")
os.environ.setdefault("OTEL_METRICS_EXPORTER", "none")
os.environ.setdefault("OTEL_LOGS_EXPORTER", "none")
os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = ""
os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = ""
os.environ["OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"] = ""

import pytest  # noqa: E402

TEST_METRICS_BEARER_TOKEN = "test-metrics-bearer-token"


@pytest.fixture
def metrics_auth_headers():
    """Return deterministic test-only Bearer authorization headers for Prometheus metrics."""
    return {"Authorization": f"Bearer {TEST_METRICS_BEARER_TOKEN}"}


from app.middleware import tracing as tracing_module  # noqa: E402


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

    # Ensure OTLPSpanExporter never binds to a live socket during test runs
    tracing_module.OTLPSpanExporter = None

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
