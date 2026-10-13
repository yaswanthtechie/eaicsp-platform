import json
import logging
from app.core.logging_config import (
    JSONFormatter,
    get_request_id,
    set_request_id,
)

def test_request_id_context():
    set_request_id(
        "test-request-123"
    )

    assert get_request_id() == (
        "test-request-123"
    )


def test_json_formatter_contains_required_fields():
    set_request_id(
        "request-456"
    )

    formatter = JSONFormatter()

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Test message",
        args=(),
        exc_info=None,
    )

    output = formatter.format(record)

    data = json.loads(output)

    assert data["service"] == (
        "platform-service"
    )

    assert data["request_id"] == (
        "request-456"
    )

    assert data["level"] == "INFO"

    assert data["message"] == (
        "Test message"
    )

    assert "timestamp" in data


def test_request_fields_are_structured():
    set_request_id(
        "request-789"
    )

    formatter = JSONFormatter()

    record = logging.LogRecord(
        name="auth_requests",
        level=logging.INFO,
        pathname=__file__,
        lineno=20,
        msg="HTTP request completed",
        args=(),
        exc_info=None,
    )

    record.caller = "inventory-service"
    record.caller_endpoint = "inventory.verify"
    record.method = "POST"
    record.path = "/api/v1/auth/verify"
    record.status = 200
    record.duration_ms = 25.4

    output = formatter.format(record)

    data = json.loads(output)

    assert data["service"] == (
        "platform-service"
    )

    assert data["request_id"] == (
        "request-789"
    )

    assert data["caller"] == (
        "inventory-service"
    )

    assert data["caller_endpoint"] == (
        "inventory.verify"
    )

    assert data["method"] == "POST"
    assert data["path"] == (
        "/api/v1/auth/verify"
    )

    assert data["status"] == 200
    assert data["duration_ms"] == 25.4


def test_json_log_output_is_valid_json():
    set_request_id(
        "json-test"
    )

    formatter = JSONFormatter()

    record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=30,
        msg="Something happened",
        args=(),
        exc_info=None,
    )

    output = formatter.format(record)

    data = json.loads(output)

    assert isinstance(data, dict)