from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.abuse_event import AbuseEvent
from app.models.auth_audit_logs import AuthAuditLog
from app.services.audit_service import LOGIN_FAILED
from app.services.rate_limit_service import RATE_LIMIT_EXCEEDED

MFA_FAILED = "MFA_FAILED"
SSO_REJECTED = "SSO_REJECTED"

def get_abuse_dashboard(
    db: Session,
) -> dict:
    """
    Build the abuse-detection dashboard for the last 24 hours.

    Abuse signals:
        1. RATE_LIMIT_EXCEEDED
        2. MFA_FAILED
        3. SSO_REJECTED

    LOGIN_FAILED is retained as a separate security metric.
    """

    now = datetime.now(timezone.utc)
    last_24_hours = now - timedelta(hours=24)

    # --------------------------------------------------------
    # 1. Rate-limit abuse events
    # --------------------------------------------------------

    abuse_events = (
        db.query(AbuseEvent)
        .filter(
            AbuseEvent.detected_at >= last_24_hours
        )
        .all()
    )

    rate_limit_events = [
        event
        for event in abuse_events
        if event.event_type == RATE_LIMIT_EXCEEDED
    ]

    rate_limit_violations = len(rate_limit_events)

    # --------------------------------------------------------
    # 2. Authentication abuse events
    # --------------------------------------------------------

    auth_events = (
        db.query(AuthAuditLog)
        .filter(
            AuthAuditLog.created_at >= last_24_hours,
            AuthAuditLog.event_type.in_(
                [
                    MFA_FAILED,
                    SSO_REJECTED,
                    LOGIN_FAILED,
                ]
            ),
        )
        .all()
    )

    mfa_failed_events = [
        event
        for event in auth_events
        if event.event_type == MFA_FAILED
    ]

    sso_rejected_events = [
        event
        for event in auth_events
        if event.event_type == SSO_REJECTED
    ]

    login_failed_events = [
        event
        for event in auth_events
        if event.event_type == LOGIN_FAILED
    ]

    mfa_abuse_events = len(mfa_failed_events)
    sso_abuse_events = len(sso_rejected_events)
    login_abuse_events = len(login_failed_events)

    # --------------------------------------------------------
    # 3. Suspicious IPs
    # --------------------------------------------------------

    suspicious_ips = set()

    for event in rate_limit_events:
        if event.ip_address:
            suspicious_ips.add(event.ip_address)

    for event in mfa_failed_events:
        if event.ip_address:
            suspicious_ips.add(event.ip_address)

    for event in sso_rejected_events:
        if event.ip_address:
            suspicious_ips.add(event.ip_address)

    # --------------------------------------------------------
    # 4. Combined events per IP
    # --------------------------------------------------------

    ip_counts = {}

    for event in rate_limit_events:
        if event.ip_address:
            ip_counts[event.ip_address] = (
                ip_counts.get(event.ip_address, 0) + 1
            )

    for event in mfa_failed_events:
        if event.ip_address:
            ip_counts[event.ip_address] = (
                ip_counts.get(event.ip_address, 0) + 1
            )

    for event in sso_rejected_events:
        if event.ip_address:
            ip_counts[event.ip_address] = (
                ip_counts.get(event.ip_address, 0) + 1
            )

    # --------------------------------------------------------
    # 5. Endpoint counts
    # --------------------------------------------------------

    endpoint_counts = {}

    for event in rate_limit_events:
        if event.endpoint:
            endpoint_counts[event.endpoint] = (
                endpoint_counts.get(event.endpoint, 0) + 1
            )

    for event in mfa_failed_events:
        endpoint = "/api/v1/auth/mfa/verify"

        endpoint_counts[endpoint] = (
            endpoint_counts.get(endpoint, 0) + 1
        )

    for event in sso_rejected_events:
        endpoint = "/api/v1/auth/sso/login"

        endpoint_counts[endpoint] = (
            endpoint_counts.get(endpoint, 0) + 1
        )

    # --------------------------------------------------------
    # 6. Top IPs
    # --------------------------------------------------------

    top_ips = [
        {
            "ip_address": ip,
            "events": count,
        }
        for ip, count in sorted(
            ip_counts.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:10]
    ]

    # --------------------------------------------------------
    # 7. Top endpoints
    # --------------------------------------------------------

    top_endpoints = [
        {
            "endpoint": endpoint,
            "events": count,
        }
        for endpoint, count in sorted(
            endpoint_counts.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:10]
    ]

    # --------------------------------------------------------
    # 8. Total abuse events
    # --------------------------------------------------------

    total_events = (
        rate_limit_violations
        + mfa_abuse_events
        + sso_abuse_events
    )

    return {
        "period": "last_24_hours",
        "total_events": total_events,
        "rate_limit_violations": rate_limit_violations,
        "suspicious_ips": len(suspicious_ips),
        "mfa_abuse_events": mfa_abuse_events,
        "login_abuse_events": login_abuse_events,
        "sso_abuse_events": sso_abuse_events,
        "top_ips": top_ips,
        "top_endpoints": top_endpoints,
    }