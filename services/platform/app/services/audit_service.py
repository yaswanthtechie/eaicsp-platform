from sqlalchemy.orm import Session

from app.models.auth_audit_logs import AuthAuditLog


LOGIN_SUCCESS = "LOGIN_SUCCESS"
LOGIN_FAILED = "LOGIN_FAILED"
ROLE_CHANGED = "ROLE_CHANGED"
TOKEN_REVOKED = "TOKEN_REVOKED"
PASSWORD_RESET="PASSWORD_RESET"

def create_audit_log(
    db: Session,
    event_type: str,
    ip_address: str | None = None,
    user_id: int | None = None,
    email: str | None = None,
    details: str | None = None,
):
    audit = AuthAuditLog(
        event_type=event_type,
        user_id=user_id,
        email=email.lower() if email else None,
        ip_address=ip_address,
        details=details,
    )

    db.add(audit)
    db.flush()

    return audit
