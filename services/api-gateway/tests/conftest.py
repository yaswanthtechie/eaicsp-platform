"""
Pytest configuration and shared fixtures for API Gateway tests.
"""

import os
import tempfile

# Tests must never write into logs/access.log (Filebeat ships that file to Kibana).
os.environ.setdefault(
    "GATEWAY_ACCESS_LOG_PATH",
    os.path.join(tempfile.mkdtemp(prefix="gateway-test-logs-"), "access.log"),
)

# Prevent OpenTelemetry from attempting network connections to unavailable localhost:4318 during tests
os.environ.setdefault("OTEL_TRACES_EXPORTER", "none")
os.environ.setdefault("OTEL_METRICS_EXPORTER", "none")
os.environ.setdefault("OTEL_LOGS_EXPORTER", "none")
os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = ""
os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = ""
os.environ["OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"] = ""

import pytest

from app.core.config import settings
from app.middleware.rate_limit import in_memory_limiter
from app.middleware.ratelimit import limiter
from app.services.circuit_breaker import circuit_breaker_manager
from app.services.metrics import metrics_collector


@pytest.fixture(autouse=True)
def reset_gateway_state():
    """Reset circuit breaker, metrics, rate limiters, and Kafka consumer before and after each test."""
    circuit_breaker_manager.reset()
    metrics_collector.reset()
    in_memory_limiter.reset()
    limiter.enabled = False
    original_consumer_enabled = settings.KAFKA_CONSUMER_ENABLED
    settings.KAFKA_CONSUMER_ENABLED = False
    yield
    settings.KAFKA_CONSUMER_ENABLED = original_consumer_enabled
    circuit_breaker_manager.reset()
    metrics_collector.reset()
    in_memory_limiter.reset()
    limiter.enabled = True
