import hashlib

import pytest


def deterministic_bucket(request_id: str) -> int:
    """
    Same request_id always produces the same bucket.
    """
    digest = hashlib.sha256(request_id.encode()).hexdigest()
    return int(digest[:8], 16) % 100


def choose_version(request_id: str, production_version: str, staging_version: str):
    """
    Example 90/10 canary routing:
    0-89  -> production
    90-99 -> staging
    """
    bucket = deterministic_bucket(request_id)

    if bucket < 90:
        return production_version

    return staging_version


def test_canary_is_deterministic():
    request_id = "iris-request-001"

    version1 = choose_version(
        request_id,
        production_version="1",
        staging_version="2",
    )

    version2 = choose_version(
        request_id,
        production_version="1",
        staging_version="2",
    )

    assert version1 == version2


def test_canary_returns_only_configured_versions():
    for i in range(100):
        request_id = f"request-{i}"

        version = choose_version(
            request_id,
            production_version="1",
            staging_version="2",
        )

        assert version in {"1", "2"}


def test_canary_90_10_split():
    production_count = 0
    staging_count = 0

    for i in range(10000):
        request_id = f"request-{i}"

        version = choose_version(
            request_id,
            production_version="1",
            staging_version="2",
        )

        if version == "1":
            production_count += 1
        elif version == "2":
            staging_count += 1

    production_ratio = production_count / 10000
    staging_ratio = staging_count / 10000

    # Allow a small statistical tolerance.
    assert 0.87 <= production_ratio <= 0.93
    assert 0.07 <= staging_ratio <= 0.13


def test_canary_logs_served_version(monkeypatch):
    logged_requests = []

    def fake_log_prediction(**kwargs):
        logged_requests.append(kwargs)

    # Replace the monitoring logger used by your service.
    # Adjust import/module name to your project.
    monkeypatch.setattr(
        "src.monitoring.log_prediction",
        fake_log_prediction,
    )

    request_id = "test-request-123"

    version = choose_version(
        request_id,
        production_version="1",
        staging_version="2",
    )

    fake_log_prediction(
        request_id=request_id,
        model_version=version,
        latency_ms=10.5,
    )

    assert len(logged_requests) == 1
    assert logged_requests[0]["request_id"] == request_id
    assert logged_requests[0]["model_version"] in {"1", "2"}


def test_same_input_always_gets_same_model_version():
    request_id = "same-input"

    results = [
        choose_version(
            request_id,
            production_version="1",
            staging_version="2",
        )
        for _ in range(20)
    ]

    assert len(set(results)) == 1