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
from app.core.permissions import PERMISSIONS,ROLE_PERMISSIONS
# ============================================================
# Authentication Schemes
# ============================================================
# Kept for backward compatibility because other files may
# import oauth2_scheme.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)

# Used by protected endpoints.
# This allows Swagger to accept an already-issued access token
# after MFA verification.
bearer_scheme = HTTPBearer(
    auto_error=False,
)

# ============================================================
# Authentication
# ============================================================

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
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
    # 1. Check whether Authorization header exists
    # --------------------------------------------------------

    if credentials is None:
        raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # --------------------------------------------------------
    # 2. Extract Bearer token
    # --------------------------------------------------------

    token = credentials.credentials

    try:
        # ----------------------------------------------------
        # 3. Decode and validate JWT
        # ----------------------------------------------------

        payload = decode_token(token)
        # ----------------------------------------------------
        # 4. Only access tokens are allowed
        # ----------------------------------------------------

        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # ----------------------------------------------------
        # 5. Get user identity from JWT subject
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
    # 6. Find user using JWT subject
    # --------------------------------------------------------

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    # --------------------------------------------------------
    # 7. Reject missing or inactive users
    # --------------------------------------------------------

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # --------------------------------------------------------
    # 8. Reject locked accounts
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
    # 9. Cross-check JWT subject with DB user
    # --------------------------------------------------------

    if user.email.lower() != email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # --------------------------------------------------------
    # 10. Return authenticated user
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


# ============================================================
# Permission OR Legacy Role Authorization
# ============================================================
def require_permission_or_role(permission: str, *allowed_roles: str):
    """
    Allow the request if the user's role grants `permission` (V2 model),
    OR if the user's role satisfies `allowed_roles` the same way
    require_role() does, including ROLE_HIERARCHY (V1 behaviour).
    """

    if permission not in PERMISSIONS:
        # A misspelled permission would silently fall through to the legacy
        # role check and lock out only the new roles. Fail at startup instead.
        raise ValueError(f"Unknown permission: {permission!r}")
    def checker(current_user: User = Depends(get_current_user)):
        user_role = current_user.role.name if current_user.role else None

        if user_role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: insufficient permissions",
            )

        if permission in ROLE_PERMISSIONS.get(user_role, set()):
            return current_user

        role_scope = ROLE_HIERARCHY.get(user_role, {user_role})
        if any(role in role_scope for role in allowed_roles):
            return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: insufficient permissions",
        )

    return checker

# ============================================================
# Role-grant guard
# ============================================================
# Roles that hold (or can reach) business-wide authority. Only the V1 admins
# (ceo / vp_operations) may hand these out.
PRIVILEGED_ROLES = frozenset({"ceo", "vp_operations", "platform_admin"})
LEGACY_ROLE_ADMINS = frozenset({"ceo", "vp_operations"})

def ensure_can_grant_role(actor: User, target_role: str, target_user_id=None) -> None:
    """
    Stop a user who only holds `user:manage` / `role:assign` (for example
    platform_admin) from escalating privileges.

    ceo and vp_operations are unchanged: they can assign any role, as before.
    Everyone else may not grant a privileged role, and may not change their
    own role.
    """
    actor_role = actor.role.name if actor.role else None

    if actor_role in LEGACY_ROLE_ADMINS:
        return

    if target_role in PRIVILEGED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: your role cannot grant the '{target_role}' role",
        )

    if target_user_id is not None and target_user_id == actor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: you cannot change your own role",
        )

def ensure_can_manage_user(actor: User, target: User) -> None:

    """
    Stop a user who only holds `user:manage` / `role:assign` (for example
    platform_admin) from acting on a privileged account: resetting its
    password, changing its role, deactivating it or revoking its sessions.

    ceo and vp_operations are unchanged: they can manage any user, as before.
    """
    
    actor_role = actor.role.name if actor.role else None

    if actor_role in LEGACY_ROLE_ADMINS:
        return

    target_role = target.role.name if target.role else None

    if target_role in PRIVILEGED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: your role cannot manage a '{target_role}' user",
        )
