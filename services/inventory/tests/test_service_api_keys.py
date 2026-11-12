"""
Unit and integration tests for Service API Key authentication (R15-RH1, R15-B6).

Verifies:
1. Inventory sends INVENTORY_SERVICE_API_KEY in X-API-Key header to Forecast Serving.
2. Inventory sends INVENTORY_SERVICE_API_KEY in X-API-Key header to Compliance.
3. HTTP 401 from Forecast Serving is handled gracefully (fallback to sales history, no crash).
4. HTTP 401 from Compliance Service is handled gracefully (raises ComplianceServiceError, no crash).
5. Secrets are never logged or exposed in log outputs.
6. Empty API key behavior logs a warning, omits header, and does not crash.
7. Outbound HTTP 401 is not retried.
"""

import logging
from unittest.mock import patch

import httpx
import pytest

from app.core.config import settings
from app.services.compliance_client import (
    ComplianceServiceError,
    check_supplier_compliance,
)
from app.services.forecast_client import ForecastClient

TEST_SECRET_KEY = "sk_test_inventory_secret_key_999"
REAL_HTTPX_CLIENT = httpx.Client


def test_forecast_client_sends_x_api_key_header():
    """ForecastClient sends X-API-Key with INVENTORY_SERVICE_API_KEY on outbound calls."""
    captured_request = {}

    def mock_handler(request: httpx.Request):
        captured_request["headers"] = dict(request.headers)
        return httpx.Response(
            200,
            json={
                "contract_version": "v1",
                "sku_id": "SKU-000123",
                "warehouse_id": "WH-BLR-01",
                "granularity": "daily",
                "horizon": 30,
                "interval_level": 0.8,
                "model_version": "test-v1",
                "generated_at": "2026-11-04T12:00:00Z",
                "forecast": [
                    {
                        "date": "2026-11-05",
                        "predicted": 10.0,
                        "lower_bound": 8.0,
                        "upper_bound": 12.0,
                    }
                ],
            },
        )

    with patch.object(settings, "INVENTORY_SERVICE_API_KEY", TEST_SECRET_KEY):
        client = ForecastClient(base_url="http://localhost:8007")

        with patch(
            "app.services.forecast_client.httpx.Client",
            side_effect=lambda **kwargs: REAL_HTTPX_CLIENT(
                transport=httpx.MockTransport(mock_handler)
            ),
        ):
            res = client.fetch_forecast("SKU-000123", "WH-BLR-01", horizon=30)

    assert res is not None
    assert "x-api-key" in captured_request["headers"]
    assert captured_request["headers"]["x-api-key"] == TEST_SECRET_KEY
    assert captured_request["headers"]["x-caller-service"] == "inventory-service"


def test_compliance_client_sends_x_api_key_header():
    """check_supplier_compliance sends X-API-Key with INVENTORY_SERVICE_API_KEY on outbound calls."""
    captured_request = {}

    def mock_handler(request: httpx.Request):
        captured_request["headers"] = dict(request.headers)
        return httpx.Response(
            200,
            json={
                "decision": "CLEAR",
                "cleared": True,
                "reason": "Test cleared",
            },
        )

    with patch.object(settings, "INVENTORY_SERVICE_API_KEY", TEST_SECRET_KEY):
        with patch(
            "app.services.compliance_client.httpx.Client",
            side_effect=lambda **kwargs: REAL_HTTPX_CLIENT(
                transport=httpx.MockTransport(mock_handler)
            ),
        ):
            result = check_supplier_compliance(
                supplier_id="SUP-00045",
                supplier_name="Acme Supplier",
                country="India",
            )

    assert result["decision"] == "CLEAR"
    assert "x-api-key" in captured_request["headers"]
    assert captured_request["headers"]["x-api-key"] == TEST_SECRET_KEY
    assert captured_request["headers"]["x-caller-service"] == "inventory-service"


def test_forecast_client_handles_401_with_fallback_and_no_key_in_logs(
    caplog, db_session
):
    """When Forecast Serving returns 401, client logs cleanly without key and falls back without crashing."""
    sensitive_key = "sk_very_secret_inventory_key_do_not_leak"

    def mock_handler(request: httpx.Request):
        return httpx.Response(
            401,
            json={"detail": "Invalid service API key"},
        )

    with caplog.at_level(logging.WARNING):
        with patch.object(settings, "INVENTORY_SERVICE_API_KEY", sensitive_key):
            client = ForecastClient(base_url="http://localhost:8007")

            with patch(
                "app.services.forecast_client.httpx.Client",
                side_effect=lambda **kwargs: REAL_HTTPX_CLIENT(
                    transport=httpx.MockTransport(mock_handler)
                ),
            ):
                result = client.resolve_demand(
                    db=db_session,
                    sku_id="SKU-000123",
                    warehouse_id="WH-BLR-01",
                    horizon=30,
                    fallback_days=28,
                )

    # Asserts fallback occurred without crash
    assert result.forecast_source == "fallback"

    # Asserts 401 warning was logged
    assert "rejected service API key (HTTP 401)" in caplog.text

    # Asserts sensitive key was NEVER printed in logs
    assert sensitive_key not in caplog.text


def test_compliance_client_handles_401_gracefully_and_no_key_in_logs(caplog):
    """When Compliance returns 401, client logs cleanly without key and raises ComplianceServiceError."""
    sensitive_key = "sk_very_secret_inventory_key_do_not_leak"

    def mock_handler(request: httpx.Request):
        return httpx.Response(
            401,
            json={"detail": "Missing service API key"},
        )

    with caplog.at_level(logging.WARNING):
        with patch.object(settings, "INVENTORY_SERVICE_API_KEY", sensitive_key):
            with patch(
                "app.services.compliance_client.httpx.Client",
                side_effect=lambda **kwargs: REAL_HTTPX_CLIENT(
                    transport=httpx.MockTransport(mock_handler)
                ),
            ):
                with pytest.raises(ComplianceServiceError) as exc_info:
                    check_supplier_compliance(
                        supplier_id="SUP-00045",
                        supplier_name="Acme Supplier",
                        country="India",
                    )

    assert "Compliance Service returned an error." in str(exc_info.value)
    assert "Compliance Service rejected service API key (HTTP 401)" in caplog.text

    # Asserts sensitive key was NEVER printed in logs or exception detail
    assert sensitive_key not in caplog.text
    assert sensitive_key not in str(exc_info.value)


def test_empty_api_key_logs_warning_and_omits_header(caplog):
    """With no key set: warning logged, no X-API-Key header sent, 401 handled without a crash."""
    captured_request = {}

    def mock_handler(request: httpx.Request):
        captured_request["headers"] = dict(request.headers)
        return httpx.Response(401, json={"detail": "Missing service API key"})

    with (
        caplog.at_level(logging.WARNING),
        patch.object(settings, "INVENTORY_SERVICE_API_KEY", ""),
    ):
        client = ForecastClient(base_url="http://localhost:8007")
        with patch(
            "app.services.forecast_client.httpx.Client",
            side_effect=lambda **kwargs: REAL_HTTPX_CLIENT(
                transport=httpx.MockTransport(mock_handler)
            ),
        ):
            result = client.fetch_forecast("SKU-000123", "WH-BLR-01", horizon=30)

    assert result is None
    assert "x-api-key" not in captured_request["headers"]
    assert "INVENTORY_SERVICE_API_KEY is not set" in caplog.text


def test_forecast_401_is_not_retried():
    """A 401 means the key is wrong; retrying won't help, so exactly one request is sent."""
    calls = []

    def mock_handler(request: httpx.Request):
        calls.append(request)
        return httpx.Response(401, json={"detail": "Invalid service API key"})

    client = ForecastClient(
        base_url="http://localhost:8007",
        api_key=TEST_SECRET_KEY,
        max_retries=1,
    )
    with patch(
        "app.services.forecast_client.httpx.Client",
        side_effect=lambda **kwargs: REAL_HTTPX_CLIENT(
            transport=httpx.MockTransport(mock_handler)
        ),
    ):
        result = client.fetch_forecast("SKU-000123", "WH-BLR-01", horizon=30)

    assert result is None
    assert len(calls) == 1
