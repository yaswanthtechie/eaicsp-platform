import os

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
# Suppress OTel SDK internal self-diagnostics metrics export to localhost:4318
os.environ.setdefault("OTEL_METRICS_EXPORTER", "none")
os.environ.setdefault("OTEL_TRACES_EXPORTER", "none")

import pytest  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter  # noqa: E402

TEST_METRICS_BEARER_TOKEN = "test-metrics-bearer-token"


@pytest.fixture
def metrics_auth_headers():
    """Return deterministic test-only Bearer authorization headers for Prometheus metrics."""
    return {"Authorization": f"Bearer {TEST_METRICS_BEARER_TOKEN}"}


from app.middleware import tracing as tracing_module  # noqa: E402


class _TestOTLPSpanExporter(InMemorySpanExporter):
    """
    Drop-in test replacement for OTLPSpanExporter.
    Accepts arbitrary kwargs (including endpoint=...) and buffers spans in-memory,
    guaranteeing zero socket connections to localhost:4318 if setup_tracing() falls back.
    """
    def __init__(self, *args, **kwargs):
        super().__init__()


# Replace OTLPSpanExporter in the tracing module namespace for all tests
tracing_module.OTLPSpanExporter = _TestOTLPSpanExporter

import app.main  # noqa: E402

# Prevent FastAPI TestClient lifespan exit from prematurely tearing down test providers
app.main.shutdown_tracing = lambda: None


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
    Ensure every test runs with an isolated in-memory TracerProvider.
    Cleans up any stale or already-shutdown provider state from previous tests,
    and provisions a fresh in-memory TracerProvider.
    Any custom test fixture (such as memory_exporter in test_round10_m2_tracing.py or
    memory_tracer in test_jaeger_privacy.py) executes after this setup and will safely
    replace this provider with its own.
    """
    try:
        from app.services.prometheus_metrics import reset_prometheus_metrics
        reset_prometheus_metrics()
    except Exception:
        pass

    # Cleanly shut down any stale, leaked, or already-shutdown provider from a previous test
    tracing_module.shutdown_tracing()

    # Always provision a fresh, active in-memory TracerProvider for the upcoming test
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
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
