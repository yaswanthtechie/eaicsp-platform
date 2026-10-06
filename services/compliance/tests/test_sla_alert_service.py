from unittest.mock import Mock, patch

from app.services.sla_alert_service import send_sla_alert


def test_sla_alert_returns_false_when_webhook_not_configured():
    with patch(
        "app.services.sla_alert_service.SLA_ALERT_WEBHOOK_URL",
        None,
    ):
        result = send_sla_alert(
            caller_service="supplier-portal",
            supplier_id="SUP-001",
            latency_ms=750.0,
            threshold_ms=500.0,
        )

    assert result is False


@patch("app.services.sla_alert_service.httpx.post")
def test_sla_alert_sends_webhook_successfully(mock_post):
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    with patch(
        "app.services.sla_alert_service.SLA_ALERT_WEBHOOK_URL",
        "https://example.com/sla-alert",
    ):
        result = send_sla_alert(
            caller_service="supplier-portal",
            supplier_id="SUP-001",
            latency_ms=750.25,
            threshold_ms=500.0,
        )

    assert result is True

    mock_post.assert_called_once_with(
        "https://example.com/sla-alert",
        json={
            "service": "compliance",
            "event": "sla_degraded",
            "caller_service": "supplier-portal",
            "supplier_id": "SUP-001",
            "latency_ms": 750.25,
            "threshold_ms": 500.0,
            "message": (
                "Compliance Service latency exceeded "
                "the configured SLA threshold."
            ),
        },
        timeout=3.0,
    )

    mock_response.raise_for_status.assert_called_once()


@patch("app.services.sla_alert_service.httpx.post")
def test_sla_alert_returns_false_when_webhook_fails(mock_post):
    mock_post.side_effect = Exception("Webhook unavailable")

    with patch(
        "app.services.sla_alert_service.SLA_ALERT_WEBHOOK_URL",
        "https://example.com/sla-alert",
    ):
        result = send_sla_alert(
            caller_service="supplier-portal",
            supplier_id="SUP-001",
            latency_ms=750.0,
            threshold_ms=500.0,
        )

    assert result is False