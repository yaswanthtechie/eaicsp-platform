"""
Severity mapping helper for Live Dashboard Realtime Events (Round 15 Flow C).

Determines top-level severity ('critical', 'warning', 'info') for outgoing
WebSocket events forwarded by the API Gateway BFF.
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

# The three allowed severity levels defined by the contract
SEVERITY_CRITICAL: str = "critical"
SEVERITY_WARNING: str = "warning"
SEVERITY_INFO: str = "info"

SeverityLevel = Literal["critical", "warning", "info"]

# Supplier risk tier ordering: low < medium < high
TIER_ORDER: Dict[str, int] = {
    "low": 1,
    "medium": 2,
    "high": 3,
}


def _resolve_inventory_severity(payload: Dict[str, Any]) -> SeverityLevel:
    """
    inventory.stock.low:
    - payload.quantity_on_hand <= 0 -> 'critical'
    - Stock available but low (quantity_on_hand > 0) -> 'warning'
    - Missing or non-numeric quantity -> 'warning'
    """
    try:
        return SEVERITY_CRITICAL if int(payload.get("quantity_on_hand")) <= 0 else SEVERITY_WARNING
    except (ValueError, TypeError):
        return SEVERITY_WARNING


def _resolve_iot_anomaly_severity(payload: Dict[str, Any]) -> SeverityLevel:
    """
    iot.anomaly.detected:
    Use existing payload.severity:
    - critical -> critical
    - high -> critical
    - medium -> warning
    - low -> info
    """
    raw_severity = payload.get("severity")
    if isinstance(raw_severity, str):
        clean = raw_severity.strip().lower()
        if clean in ("critical", "high"):
            return SEVERITY_CRITICAL
        if clean == "medium":
            return SEVERITY_WARNING
        if clean == "low":
            return SEVERITY_INFO
    return SEVERITY_INFO


def _resolve_supplier_risk_severity(payload: Dict[str, Any]) -> SeverityLevel:
    """
    supplierrisk.score.changed:
    Compare payload.previous_tier and payload.new_tier.
    Ordering: low < medium < high.
    - Risk tier increases -> 'warning'
    - Risk tier decreases -> 'info'
    - Same-tier or unexpected values -> 'info' safe fallback.
    """
    prev_tier = payload.get("previous_tier")
    new_tier = payload.get("new_tier")

    if not isinstance(prev_tier, str) or not isinstance(new_tier, str):
        return SEVERITY_INFO

    prev_rank = TIER_ORDER.get(prev_tier.strip().lower())
    new_rank = TIER_ORDER.get(new_tier.strip().lower())

    if prev_rank is None or new_rank is None:
        return SEVERITY_INFO

    if new_rank > prev_rank:
        return SEVERITY_WARNING
    # Decreased (new_rank < prev_rank) or same tier (new_rank == prev_rank) -> info
    return SEVERITY_INFO


def _resolve_eta_severity(payload: Dict[str, Any]) -> SeverityLevel:
    """
    eta.shipment.predicted:
    Always -> 'info'.
    """
    return SEVERITY_INFO


def _resolve_forecast_severity(payload: Dict[str, Any]) -> SeverityLevel:
    """
    forecast.batch.completed:
    - payload.status == "SUCCESS" -> 'info'
    - payload.status == "PARTIAL" -> 'warning'
    """
    status = payload.get("status")
    if isinstance(status, str):
        clean = status.strip().upper()
        if clean == "PARTIAL":
            return SEVERITY_WARNING
        if clean == "SUCCESS":
            return SEVERITY_INFO
    return SEVERITY_INFO


def _resolve_pipeline_severity(payload: Dict[str, Any]) -> SeverityLevel:
    """
    data.pipeline.completed:
    Completed -> 'info'.
    """
    return SEVERITY_INFO


def resolve_severity(
    event_type: str,
    payload: Optional[Dict[str, Any]] = None,
) -> SeverityLevel:
    """
    Resolve the top-level severity for an event based on its event_type and payload.

    Returns exactly one of: 'critical', 'warning', 'info'.
    Falls back to 'info' for unknown event types or invalid payloads.
    """
    p = payload if isinstance(payload, dict) else {}

    if event_type == "inventory.stock.low":
        return _resolve_inventory_severity(p)
    elif event_type == "iot.anomaly.detected":
        return _resolve_iot_anomaly_severity(p)
    elif event_type == "supplierrisk.score.changed":
        return _resolve_supplier_risk_severity(p)
    elif event_type == "eta.shipment.predicted":
        return _resolve_eta_severity(p)
    elif event_type == "forecast.batch.completed":
        return _resolve_forecast_severity(p)
    elif event_type == "data.pipeline.completed":
        return _resolve_pipeline_severity(p)
    else:
        # Unknown event type: safe fallback to 'info'
        return SEVERITY_INFO


def resolve_event_severity(event: Dict[str, Any]) -> SeverityLevel:
    """
    Convenience function that accepts a full event dictionary and resolves severity.
    """
    if not isinstance(event, dict):
        return SEVERITY_INFO

    event_type = event.get("event_type")
    if not isinstance(event_type, str):
        return SEVERITY_INFO

    payload = event.get("payload")
    return resolve_severity(event_type, payload if isinstance(payload, dict) else {})


def build_outgoing_event(
    event: Dict[str, Any],
    severity: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Construct the outgoing event envelope with the BFF-decided top-level severity.

    - Preserves all original producer envelope fields.
    - Preserves original payload exactly as received (including any producer severity).
    - Inserts top-level 'severity' immediately before 'payload'.
    - Does NOT mutate the input event dictionary.
    """
    if not isinstance(event, dict):
        return {}

    resolved_severity: SeverityLevel
    if severity in (SEVERITY_CRITICAL, SEVERITY_WARNING, SEVERITY_INFO):
        resolved_severity = severity  # type: ignore[assignment]
    else:
        resolved_severity = resolve_event_severity(event)

    outgoing: Dict[str, Any] = {}
    severity_inserted = False

    for k, v in event.items():
        if k == "severity":
            # Omit preexisting top-level severity to let BFF decide
            continue
        if k == "payload" and not severity_inserted:
            outgoing["severity"] = resolved_severity
            severity_inserted = True
        outgoing[k] = v

    if not severity_inserted:
        outgoing["severity"] = resolved_severity

    return outgoing

