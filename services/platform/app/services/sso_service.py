from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core import config as app_config
from app.core.security import create_access_token, create_refresh_token
from app.models.users import User
from app.services.audit_service import SSO_LOGIN, SSO_REJECTED, create_audit_log
from app.services.auth_service import save_refresh_token

MOCK_SSO_PROVIDER = "mock-enterprise-sso"
ASSERTION_AUDIENCE = "eaicsp-platform"
ASSERTION_TTL_SECONDS = 120

# ------------------------------------------------------------
# Mock enterprise directory: this is the IDENTITY PROVIDER's data,
# used only to ISSUE assertions (tests/demo). The login endpoint
# never trusts these values from a client.
# ------------------------------------------------------------
MOCK_SSO_USERS = {
    "enterprise-001": {"email": "ceo@company.com", "full_name": "CEO User"},
    "enterprise-002": {"email": "vpoperations@company.com", "full_name": "Vpoperations User"},
}


def _require_enabled() -> str:
    if not app_config.MOCK_SSO_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    secret = app_config.MOCK_SSO_SECRET or ""
    if len(secret) < 32:
        # Never verify with an empty or guessable key.
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="SSO is not configured")
    return secret

# ------------------------------------------------------------
# Mock IdP side: issue a signed, short-lived assertion.
# ------------------------------------------------------------
def create_mock_sso_assertion(external_id: str) -> str:
    secret = _require_enabled()
    user = MOCK_SSO_USERS[external_id]
    now = datetime.now(timezone.utc)
    claims = {
        "iss": MOCK_SSO_PROVIDER,
        "aud": ASSERTION_AUDIENCE,
        "sub": external_id,
        "email": user["email"],
        "name": user["full_name"],
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ASSERTION_TTL_SECONDS)).timestamp()),
    }
    return jwt.encode(claims, secret, algorithm="HS256")


# ------------------------------------------------------------
# Platform side: verify the assertion, then issue our tokens.
# ------------------------------------------------------------
def mock_sso_login(db: Session, provider: str, assertion: str, client_ip: str):
    secret = _require_enabled()

    def reject(reason: str):
        create_audit_log(
            db=db,
            event_type=SSO_REJECTED,
            ip_address=client_ip,
            details=f"SSO rejected: {reason}",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="SSO authentication failed",
        )

    if provider != MOCK_SSO_PROVIDER:
        reject("unsupported provider")

    try:
        claims = jwt.decode(
            assertion,
            secret,
            algorithms=["HS256"],
            audience=ASSERTION_AUDIENCE,
            issuer=MOCK_SSO_PROVIDER,
        )
    except JWTError:
        reject("invalid, expired or tampered assertion")

    email = str(claims.get("email", "")).lower()
    user = db.query(User).filter(User.email == email).first()

    if user is None:
        reject("identity not registered in EAICSP")
    if not user.is_active or user.role is None:
        reject("inactive account or no role")
        
    # Same lockout the password login enforces. SQLite returns naive
    # datetimes, so treat a naive locked_until as UTC.
    locked_until = user.locked_until
    if locked_until is not None:
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > datetime.now(timezone.utc):
            reject("account is locked")

    access_token = create_access_token(
        {"sub": user.email, "user_id": user.id, "role": user.role.name}
    )
    refresh_token = create_refresh_token({"sub": user.email, "user_id": user.id})

    save_refresh_token(
        db=db,
        user_id=user.id,
        token=refresh_token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )

    create_audit_log(
        db=db,
        event_type=SSO_LOGIN,
        user_id=user.id,
        email=user.email,
        ip_address=client_ip,
        details=f"Federated SSO login via {MOCK_SSO_PROVIDER} (external_id={claims.get('sub')})",
    )
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "auth_type": "federated-sso",
    }