from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import (
    OAuth2PasswordBearer,
    HTTPBearer,
    HTTPAuthorizationCredentials,
)
from sqlalchemy.orm import Session
from jose import JWTError
from app.core.security import decode_token
from app.database import get_db
from app.models.users import User
from app.core.permissions import ROLE_PERMISSIONS

# ============================================================
# Authentication Schemes
# ============================================================
# Kept for backward compatibility because other files may
# import oauth2_scheme.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login"
)

# Used by protected endpoints.
# This allows Swagger to accept an already-issued access token
# after MFA verification.
bearer_scheme = HTTPBearer()

# ============================================================
# Authentication
# ============================================================

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
):
    """
    Validate the access token and return the authenticated user.

    Expected header:

        Authorization: Bearer <access_token>
    """
    # --------------------------------------------------------
    # 1. Extract Bearer token
    # --------------------------------------------------------

    token = credentials.credentials

    try:
        # ----------------------------------------------------
        # 2. Decode and validate JWT
        # ----------------------------------------------------

        payload = decode_token(token)

        # ----------------------------------------------------
        # 3. Only access tokens are allowed
        # ----------------------------------------------------

        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # ----------------------------------------------------
        # 4. Get user identity from JWT subject
        # ----------------------------------------------------

        email = payload.get("sub")

        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        email = email.lower()

    except HTTPException:
        raise

    except JWTError:
        # Invalid signature, expired token, malformed token, etc.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # --------------------------------------------------------
    # 5. Find user using JWT subject
    # --------------------------------------------------------

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    # --------------------------------------------------------
    # 6. Reject missing or inactive users
    # --------------------------------------------------------

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 6. Reject access while account is locked
    if (
        user.locked_until is not None
        and user.locked_until > datetime.now(timezone.utc)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # --------------------------------------------------------
    # 7. Reject locked accounts
    # --------------------------------------------------------

    if user.locked_until is not None:

        locked_until = user.locked_until

        # SQLite may return a naive datetime.
        # Treat it as UTC.
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(
                tzinfo=timezone.utc
            )

        if locked_until > datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # --------------------------------------------------------
    # 8. Cross-check JWT subject with DB user
    # --------------------------------------------------------

    if user.email.lower() != email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # --------------------------------------------------------
    # 9. Return authenticated user
    # --------------------------------------------------------

    return user

# ============================================================
# Role Hierarchy
# ============================================================
ROLE_HIERARCHY = {
    "ceo": {
        "ceo",
        "vp_operations",
        "procurement_manager",
        "logistics_manager",
        "compliance_officer",
        "warehouse_manager",
        "analyst",
        "supplier",
    },

    "vp_operations": {
        "vp_operations",
        "procurement_manager",
        "logistics_manager",
        "compliance_officer",
        "warehouse_manager",
        "analyst",
        "supplier",
    },

    "procurement_manager": {
        "procurement_manager",
    },

    "logistics_manager": {
        "logistics_manager",
    },

    "compliance_officer": {
        "compliance_officer",
    },

    "warehouse_manager": {
        "warehouse_manager",
    },

    "analyst": {
        "analyst",
    },

    "supplier": {
        "supplier",
    },
}

# ============================================================
# Require ANY Role
# ============================================================

def require_any_role(*allowed_roles):

    def dependency(
        user: User = Depends(get_current_user),
    ):
        role = (
            user.role.name
            if user.role
            else None
        )

        permissions = ROLE_HIERARCHY.get(
            role,
            {role} if role else set(),
        )

        if not any(
            allowed_role in permissions
            for allowed_role in allowed_roles
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: insufficient permissions",
            )

        return user

    return dependency

# ============================================================
# Require ALL Roles
# ============================================================
def require_all_roles(*required_roles):

    def dependency(
        user: User = Depends(get_current_user),
    ):
        role = (
            user.role.name
            if user.role
            else None
        )

        permissions = ROLE_HIERARCHY.get(
            role,
            {role} if role else set(),
        )

        if not all(
            required_role in permissions
            for required_role in required_roles
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: insufficient permissions",
            )

        return user
    return dependency

# ============================================================
# RBAC - Require Role
# ============================================================
def require_role(*allowed_roles):

    def dependency(
        user: User = Depends(get_current_user),
    ):
        role = (
            user.role.name
            if user.role
            else None
        )

        permissions = ROLE_HIERARCHY.get(
            role,
            {role} if role else set(),
        )

        if not any(
            allowed_role in permissions
            for allowed_role in allowed_roles
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: insufficient permissions",
            )

        return user
    return dependency

def require_permission(permission: str):
    def checker(
        current_user: User = Depends(get_current_user),
    ):
        user_role = (
            current_user.role.name
            if current_user.role
            else None
        )

        if user_role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden:Insufficient permissions",
            )

        permissions = ROLE_PERMISSIONS.get(user_role, set())

        if permission not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden:Insufficient permissions",
            )

    return dependency

# ============================================================
# Permission-Based Authorization
# ============================================================
def require_permission(permission: str):

    def checker(
        current_user: User = Depends(get_current_user),
    ):
        user_role = (
            current_user.role.name
            if current_user.role
            else None
        )

        if user_role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: insufficient permissions",
            )

        permissions = ROLE_PERMISSIONS.get(
            user_role,
            set(),
        )

        if permission not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: insufficient permissions",
            )

        return current_user

    return checker