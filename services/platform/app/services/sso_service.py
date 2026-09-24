from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.users import User
from app.core.security import (
    create_access_token,
    create_refresh_token,
)
from app.services.auth_service import save_refresh_token

MOCK_SSO_PROVIDER = "mock-enterprise-sso"

# ------------------------------------------------------------
# Mock Enterprise Directory
# ------------------------------------------------------------
MOCK_SSO_USERS = {
    "enterprise-001": {
        "email": "ceo@company.com",
        "full_name": "CEO User",
    },
    "enterprise-002": {
            "email": "vpoperations@company.com",
            "full_name": "Vpoperations User",
    },
}
# ------------------------------------------------------------
# Mock SSO Login
# ------------------------------------------------------------

def mock_sso_login(
    db: Session,
    provider: str,
    email: str,
    full_name: str,
    external_id: str,
):
    # 1. Validate provider
    if provider != MOCK_SSO_PROVIDER:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unsupported SSO provider",
        )

    # 2. Validate external enterprise identity
    enterprise_user = MOCK_SSO_USERS.get(external_id)

    if enterprise_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid enterprise identity",
        )

    # 3. Cross-check identity data
    if (
        enterprise_user["email"].lower() != email.lower()
        or enterprise_user["full_name"] != full_name
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Enterprise identity mismatch",
        )

    # 4. Normalize email
    email = email.lower()

    # 5. Find existing user
    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise SSO user is not registered in EAICSP",
        )

    # 6. Check active account
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
        )

    # 7. Check role
    if user.role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User role is not assigned",
        )

    # 8. Create access token
    access_token = create_access_token(
        {
            "sub": user.email,
            "user_id": user.id,
            "role": user.role.name,
        }
    )

    # 9. Create refresh token
    refresh_token = create_refresh_token(
        {
            "sub": user.email,
            "user_id": user.id,
        }
    )

    # 10. Store refresh token
    refresh_expires_at = (
        datetime.now(timezone.utc)
        + timedelta(days=7)
    )

    save_refresh_token(
        db=db,
        user_id=user.id,
        token=refresh_token,
        expires_at=refresh_expires_at,
    )

    db.commit()

    # 11. Return tokens
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "auth_type": "federated-sso",
    }