from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError

from app.core.security import decode_token
from app.database import get_db
from app.models.users import User


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login"
)


# ============================================================
# Authentication
# ============================================================

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    try:
        # 1. Decode and validate JWT
        payload = decode_token(token)

        # 2. Only access tokens can be used for protected endpoints
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

        # 3. Get user identity from JWT subject
        email = payload.get("sub")

        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

        email = email.lower()

    except HTTPException:
        # Preserve our intentional 401 errors
        raise

    except JWTError:
        # Invalid signature, expired token, malformed token, etc.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    except Exception:
        # Do not expose internal authentication errors
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # 4. Find user using JWT subject
    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    # 5. Reject missing or inactive users
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # 6. Cross-check JWT subject with DB user
    if user.email.lower() != email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

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
        user=Depends(get_current_user),
    ):
        role = user.role.name

        permissions = ROLE_HIERARCHY.get(
            role,
            {role},
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
        user=Depends(get_current_user),
    ):
        role = user.role.name

        permissions = ROLE_HIERARCHY.get(
            role,
            {role},
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
        user=Depends(get_current_user),
    ):
        role = user.role.name

        permissions = ROLE_HIERARCHY.get(
            role,
            {role},
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