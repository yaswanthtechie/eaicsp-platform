import csv
import io
import json
from sqlalchemy.orm import Session
from app.models.auth_audit_logs import AuthAuditLog


SUCCESS_EVENTS = {
    "LOGIN_SUCCESS",
    "MFA_VERIFIED",
    "SSO_LOGIN",
    "TOKEN_REVOKED",
    "PASSWORD_RESET",
    "ROLE_CHANGED",
    "SERVICE_KEY_CREATED",
}

FAILURE_EVENTS = {
    "LOGIN_FAILED",
    "MFA_FAILED",
    "SSO_REJECTED",
    "ACCOUNT_LOCKED",
}

def get_audit_outcome(event_type: str) -> str:
    if event_type in FAILURE_EVENTS:
        return "failure"

    if event_type in SUCCESS_EVENTS:
        return "success"

    return "unknown"


def export_audit_logs(
    db: Session,
    from_date=None,
    to_date=None,
    event_type=None,
    limit: int = 1000,
    offset: int = 0,
    output_format: str = "csv",
):
    query = (
        db.query(AuthAuditLog)
        .order_by(AuthAuditLog.created_at.asc())
    )

    if from_date is not None:
        query = query.filter(
            AuthAuditLog.created_at >= from_date
        )

    if to_date is not None:
        query = query.filter(
            AuthAuditLog.created_at <= to_date
        )

    if event_type:
        query = query.filter(
            AuthAuditLog.event_type == event_type
        )

    audit_logs = (
    query
    .offset(offset)
    .limit(limit)
    .all()
)

    columns = [
        "timestamp",
        "actor_id",
        "actor_email",
        "action",
        "outcome",
        "ip_address",
        "details",
    ]

    rows = [
        {
            "timestamp": audit.created_at.isoformat()
            if audit.created_at
            else "",
            "actor_id": audit.user_id
            if audit.user_id is not None
            else "",
            "actor_email": audit.email or "",
            "action": audit.event_type,
            "outcome": get_audit_outcome(audit.event_type),
            "ip_address": audit.ip_address or "",
            "details": audit.details or "",
        }
        for audit in audit_logs
    ]

    if output_format.lower() == "json":
        return json.dumps(rows)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)

    return output.getvalue()
