import csv
import io
from sqlalchemy.orm import Session
from app.models.auth_audit_logs import AuthAuditLog

def export_audit_logs(
    db: Session,
    from_date=None,
    to_date=None,
    event_type=None,
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

    audit_logs = query.all()

    output = io.StringIO()

    writer = csv.writer(output)

    # Compliance-oriented column names
    writer.writerow([
        "timestamp",
        "actor_id",
        "actor_email",
        "action",
        "ip_address",
        "details",
    ])

    for audit in audit_logs:
        writer.writerow([
            audit.created_at.isoformat()
            if audit.created_at
            else "",
            audit.user_id if audit.user_id is not None else "",
            audit.email or "",
            audit.event_type,
            audit.ip_address or "",
            audit.details or "",
        ])

    return output.getvalue()