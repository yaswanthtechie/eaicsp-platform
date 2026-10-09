import logging

import httpx

from app.core.config import SLA_ALERT_WEBHOOK_URL


logger = logging.getLogger(__name__)


def send_sla_alert(
    caller_service: str,
    supplier_id: str,
    latency_ms: float,
    threshold_ms: float,
) -> bool:
    

    if not SLA_ALERT_WEBHOOK_URL:
        logger.warning(
            "SLA alert not sent: "
            "SLA_ALERT_WEBHOOK_URL is not configured"
        )

        return False

    payload = {
        "service": "compliance",
        "event": "sla_degraded",
        "caller_service": caller_service,
        "supplier_id": supplier_id,
        "latency_ms": round(latency_ms, 2),
        "threshold_ms": threshold_ms,
        "message": (
            "Compliance Service latency exceeded "
            "the configured SLA threshold."
        ),
    }

    try:
        response = httpx.post(
            SLA_ALERT_WEBHOOK_URL,
            json=payload,
            timeout=3.0,
        )

        response.raise_for_status()

        logger.warning(
            "SLA alert delivered successfully: "
            "caller=%s supplier_id=%s "
            "latency=%.2fms threshold=%.2fms",
            caller_service,
            supplier_id,
            latency_ms,
            threshold_ms,
        )

        return True

    except Exception:
        logger.exception(
            "SLA alert delivery failed: "
            "caller=%s supplier_id=%s "
            "latency=%.2fms threshold=%.2fms",
            caller_service,
            supplier_id,
            latency_ms,
            threshold_ms,
        )

        return False