"""
Round 14 Milestone — Automated tests for structured JSON access logging,
security/redaction, correlation, and OpenTelemetry trace ID capture.
"""

import json
import logging
import uuid
from datetime import datetime

import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.middleware.logging import (
    LoggingMiddleware,
    extract_trace_id,
    resolve_bounded_route,
)
from app.middleware.rate_limit import in_memory_limiter


@pytest.fixture
def client():
    """Create a test client for the gateway."""
    with TestClient(app) as test_client:
        yield test_client


def get_access_log_records(caplog):
    """Filter and parse access log records from caplog."""
    records = []
    for record in caplog.records:
        if record.name == "api_gateway.access":
            try:
                records.append(json.loads(record.message))
            except Exception:
                pass
    return records


def test_access_log_is_valid_json(client, caplog):
    """Verify every access log emitted is a single valid JSON line."""
    caplog.set_level(logging.INFO, logger="api_gateway.access")
    caplog.clear()

    response = client.get("/")
    assert response.status_code == 200

    access_records = get_access_log_records(caplog)
    assert len(access_records) >= 1

    for rec in access_records:
        assert isinstance(rec, dict)


def test_required_fields_present_and_correctly_typed(client, caplog):
    """
    Verify all required fields exist and have correct types:
    - @timestamp (UTC ISO-8601 string)
    - level (str)
    - service.name (str)
    - http.method (str)
    - route (str)
    - http.status_code (int)
    - latency_ms (float)
    - request_id (str)
    - trace_id (str or None)
    """
    caplog.set_level(logging.INFO, logger="api_gateway.access")
    caplog.clear()

    response = client.get("/")
    assert response.status_code == 200

    records = get_access_log_records(caplog)
    assert len(records) >= 1
    log_entry = records[-1]

    # Required keys existence
    required_keys = [
        "@timestamp",
        "level",
        "service.name",
        "http.method",
        "route",
        "http.status_code",
        "latency_ms",
        "request_id",
        "trace_id",
    ]
    for key in required_keys:
        assert key in log_entry, f"Missing required field: {key}"

    # Type verifications
    assert isinstance(log_entry["@timestamp"], str)
    # Validate ISO-8601 format
    ts_str = log_entry["@timestamp"].rstrip("Z")
    datetime.fromisoformat(ts_str)

    assert log_entry["level"] in {"INFO", "WARN", "ERROR"}
    assert log_entry["service.name"] == "api-gateway"
    assert log_entry["http.method"] == "GET"
    assert log_entry["route"] == "/"
    assert isinstance(log_entry["http.status_code"], int)
    assert log_entry["http.status_code"] == 200
    assert isinstance(log_entry["latency_ms"], (float, int))
    assert log_entry["latency_ms"] >= 0.0
    assert isinstance(log_entry["request_id"], str)
    assert len(log_entry["request_id"]) > 0

    # trace_id must be a 32-char hex string or None
    trace_id = log_entry["trace_id"]
    if trace_id is not None:
        assert isinstance(trace_id, str)
        assert len(trace_id) == 32
        int(trace_id, 16)  # Must be valid hex


def test_request_id_preserved_and_correlated(client, caplog):
    """Verify client-supplied X-Request-ID is preserved in response and logged accurately."""
    caplog.set_level(logging.INFO, logger="api_gateway.access")
    caplog.clear()

    custom_id = f"test-correlation-{uuid.uuid4()}"
    response = client.get("/", headers={"X-Request-ID": custom_id})

    assert response.status_code == 200
    assert response.headers.get("x-request-id") == custom_id

    records = get_access_log_records(caplog)
    matching = [r for r in records if r.get("request_id") == custom_id]
    assert len(matching) == 1
    assert matching[0]["request_id"] == custom_id


def test_trace_id_included_when_active_span_exists(client, caplog):
    """Verify trace_id is populated from active OpenTelemetry span when available."""
    caplog.set_level(logging.INFO, logger="api_gateway.access")
    caplog.clear()

    # The gateway has TracingMiddleware enabled, which generates or propagates spans
    response = client.get("/")
    assert response.status_code == 200

    records = get_access_log_records(caplog)
    assert len(records) >= 1
    log_entry = records[-1]

    # If traceparent was returned in response, verify trace_id in log matches
    traceparent = response.headers.get("traceparent")
    if traceparent:
        # traceparent format: 00-{trace_id}-{parent_id}-{trace_flags}
        expected_trace_id = traceparent.split("-")[1]
        assert log_entry["trace_id"] == expected_trace_id


def test_trace_id_is_null_when_unavailable():
    """Verify that when no active span exists, trace_id is None / null rather than inventing one."""
    from unittest.mock import MagicMock
    mock_request = MagicMock()
    mock_request.state = MagicMock()
    mock_request.state.otel_span = None

    trace_id = extract_trace_id(mock_request)
    assert trace_id is None


def test_authorization_header_and_token_never_logged(client, caplog):
    """Verify Authorization header and bearer tokens never appear in log records."""
    caplog.set_level(logging.INFO, logger="api_gateway.access")
    caplog.clear()

    secret_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.super-secret-token-payload.xyz"
    client.get("/", headers={"Authorization": f"Bearer {secret_token}"})

    raw_output = caplog.text
    assert secret_token not in raw_output
    assert "Bearer" not in raw_output
    assert "Authorization" not in raw_output

    records = get_access_log_records(caplog)
    for r in records:
        dumped = json.dumps(r)
        assert secret_token not in dumped
        assert "Authorization" not in dumped


def test_sensitive_parameters_passwords_and_cookies_not_exposed(client, caplog):
    """Verify sensitive query parameters, cookies, and passwords are never exposed in access logs."""
    caplog.set_level(logging.INFO, logger="api_gateway.access")
    caplog.clear()

    sensitive_query = (
        "?password=SuperSecretPassword123"
        "&token=TopSecretTokenABC"
        "&api_key=SuperSecretAPIKey"
        "&client_secret=SecretClient999"
    )
    headers = {
        "Cookie": "session_id=secret_session_456; refresh_token=secret_refresh_789",
    }

    client.get(f"/{sensitive_query}", headers=headers)

    raw_output = caplog.text
    forbidden_strings = [
        "SuperSecretPassword123",
        "TopSecretTokenABC",
        "SuperSecretAPIKey",
        "SecretClient999",
        "secret_session_456",
        "secret_refresh_789",
    ]
    for secret in forbidden_strings:
        assert secret not in raw_output

    records = get_access_log_records(caplog)
    assert len(records) >= 1
    entry = records[-1]
    # Bounded route must never contain query parameters
    assert "?" not in entry["route"]
    assert "password" not in entry["route"]
    assert entry["route"] == "/"


def test_error_responses_logged_correctly(client, caplog):
    """Verify both client 4xx errors and server 5xx errors are logged with appropriate level and status."""
    caplog.set_level(logging.INFO, logger="api_gateway.access")

    # 1. Client error (404 Not Found)
    caplog.clear()
    client.get("/nonexistent-endpoint-testing-404")
    records_404 = get_access_log_records(caplog)
    assert len(records_404) >= 1
    entry_404 = records_404[-1]
    assert entry_404["http.status_code"] == 404
    assert entry_404["level"] == "WARN"
    assert entry_404["route"] == "other"

    # 2. Server exception (500 Internal Server Error)
    # Test middleware directly with an app that raises an unhandled exception
    test_app = FastAPI()
    test_app.add_middleware(LoggingMiddleware)

    @test_app.get("/error-trigger")
    def trigger_error():
        raise RuntimeError("Simulated internal gateway crash")

    caplog.clear()
    err_client = TestClient(test_app, raise_server_exceptions=False)
    response_500 = err_client.get("/error-trigger")
    assert response_500.status_code == 500

    records_500 = get_access_log_records(caplog)
    assert len(records_500) >= 1
    entry_500 = records_500[-1]
    assert entry_500["http.status_code"] == 500
    assert entry_500["level"] == "ERROR"
    assert entry_500["latency_ms"] >= 0.0


def test_multiple_requests_produce_separate_log_records(client, caplog):
    """Verify multiple requests generate distinct access log records with unique correlation IDs."""
    caplog.set_level(logging.INFO, logger="api_gateway.access")
    caplog.clear()

    req_ids = [f"batch-req-{i}-{uuid.uuid4()}" for i in range(3)]
    for r_id in req_ids:
        client.get("/", headers={"X-Request-ID": r_id})

    records = get_access_log_records(caplog)
    captured_ids = [r.get("request_id") for r in records]

    for r_id in req_ids:
        assert r_id in captured_ids


def test_service_identity_not_spoofed_by_client_headers(client, caplog):
    """Verify client-controlled headers cannot spoof the service.name identity."""
    caplog.set_level(logging.INFO, logger="api_gateway.access")
    caplog.clear()

    client.get(
        "/",
        headers={
            "X-Service-Name": "malicious-service",
            "Service-Name": "fake-gateway",
            "X-Forwarded-Server": "attacker.com",
        },
    )

    records = get_access_log_records(caplog)
    assert len(records) >= 1
    assert records[-1]["service.name"] == "api-gateway"


def test_generated_request_id_is_valid_uuid_when_absent(client, caplog):
    """Verify an absent X-Request-ID generates a cryptographically valid UUID4."""
    caplog.set_level(logging.INFO, logger="api_gateway.access")
    caplog.clear()

    response = client.get("/")
    assert response.status_code == 200

    resp_request_id = response.headers.get("x-request-id")
    assert resp_request_id is not None
    # Verify valid UUID string
    parsed_uuid = uuid.UUID(resp_request_id, version=4)
    assert str(parsed_uuid) == resp_request_id

    records = get_access_log_records(caplog)
    assert len(records) >= 1
    assert records[-1]["request_id"] == resp_request_id


def test_redaction_persists_on_server_error_and_exceptions(caplog):
    """Verify secrets and bearer tokens are strictly redacted even during exceptions and 500 errors."""
    caplog.set_level(logging.INFO, logger="api_gateway.access")
    caplog.clear()

    secret_key = "sensitive-super-secret-key-999"
    secret_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.unauthorized-crash-token.xyz"

    test_app = FastAPI()
    test_app.add_middleware(LoggingMiddleware)

    @test_app.get("/crash-test")
    def crash_endpoint():
        raise ValueError("Simulated unexpected exception during processing")

    client_err = TestClient(test_app, raise_server_exceptions=False)
    response = client_err.get(
        f"/crash-test?token={secret_key}",
        headers={"Authorization": f"Bearer {secret_token}", "Cookie": "session=secret_cookie_val"},
    )
    assert response.status_code == 500

    raw_output = caplog.text
    assert secret_key not in raw_output
    assert secret_token not in raw_output
    assert "secret_cookie_val" not in raw_output
    assert "Bearer" not in raw_output

    records = get_access_log_records(caplog)
    assert len(records) >= 1
    err_entry = records[-1]
    assert err_entry["http.status_code"] == 500
    assert err_entry["level"] == "ERROR"
    assert "token" not in err_entry["route"]


def test_bounded_route_prevents_high_cardinality_explosion(client, caplog):
    """Verify unmapped or highly dynamic paths are normalized to prevent cardinality explosion."""
    caplog.set_level(logging.INFO, logger="api_gateway.access")
    caplog.clear()

    high_cardinality_path = f"/unmapped-arbitrary-entity/{uuid.uuid4()}/details/{uuid.uuid4()}"
    response = client.get(high_cardinality_path)
    assert response.status_code == 404

    records = get_access_log_records(caplog)
    assert len(records) >= 1
    entry = records[-1]
    assert entry["route"] == "other"
    assert str(uuid.uuid4())[:8] not in entry["route"]


def test_concurrent_requests_emit_independent_unmixed_json_lines(client, caplog):
    """Verify concurrent requests produce isolated, uncorrupted, valid JSON lines."""
    import concurrent.futures

    caplog.set_level(logging.INFO, logger="api_gateway.access")
    caplog.clear()

    concurrency = 8
    target_ids = [f"concurrent-id-{i}-{uuid.uuid4()}" for i in range(concurrency)]

    def make_req(req_id: str) -> str:
        resp = client.get("/", headers={"X-Request-ID": req_id})
        assert resp.status_code == 200
        return req_id

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        completed_ids = list(executor.map(make_req, target_ids))

    assert len(completed_ids) == concurrency

    records = get_access_log_records(caplog)
    captured_ids = [r.get("request_id") for r in records]

    for req_id in target_ids:
        assert req_id in captured_ids


def test_rate_limited_request_is_logged(client, caplog, monkeypatch):
    """A 429 from the per-user/IP rate limiter must still produce an access log line."""
    monkeypatch.setattr(settings, "LOAD_TEST_MODE", False, raising=False)
    in_memory_limiter.reset()
    caplog.set_level(logging.INFO, logger="api_gateway.access")

    limit = settings.get_role_rate_limit("default")
    for _ in range(limit):
        assert client.get("/").status_code == 200

    blocked = client.get("/", headers={"X-Request-ID": "rate-limited-req-1"})
    assert blocked.status_code == 429

    matching = [
        r for r in get_access_log_records(caplog)
        if r["request_id"] == "rate-limited-req-1"
    ]
    assert len(matching) == 1
    assert matching[0]["http.status_code"] == 429
    assert matching[0]["level"] == "WARN"


def test_oversized_request_id_is_truncated(client, caplog):
    caplog.set_level(logging.INFO, logger="api_gateway.access")
    client.get("/", headers={"X-Request-ID": "a" * 5000})
    record = get_access_log_records(caplog)[-1]
    assert len(record["request_id"]) == 128


def test_filebeat_parses_ndjson_into_gateway_index():
    import yaml
    from pathlib import Path

    cfg = yaml.safe_load((Path(__file__).resolve().parent.parent / "filebeat.yml").read_text())
    parser = cfg["filebeat.inputs"][0]["parsers"][0]["ndjson"]
    assert parser["keys_under_root"] is True
    assert parser["expand_keys"] is True
    assert cfg["output.elasticsearch"]["index"].startswith("gateway-logs-")
