"""
Pytest configuration and shared fixtures for API Gateway tests.
"""

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
