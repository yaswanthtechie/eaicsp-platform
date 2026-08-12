from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.core.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login"
)
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.users import User


# Authentication
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = decode_token(token)

        email = payload.get("sub")

        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    user = (
        db.query(User)
        .filter(User.email == email.lower())
        .first()
    )

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive user"
        )

    return user


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
        "procurement_manager"
    },
    "logistics_manager": {
        "logistics_manager"
    },
    "compliance_officer": {
        "compliance_officer"
    },
    "warehouse_manager": {
        "warehouse_manager"
    },
    "analyst": {
        "analyst"
    },
    "supplier": {
        "supplier"
    },
}


def require_any_role(*allowed_roles):

    def dependency(user=Depends(get_current_user)):

        user_role = getattr(user["role"], "value", user["role"])

        permissions = ROLE_HIERARCHY.get(user_role, {user_role})

        if not any(role in permissions for role in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden"
            )

        return user

    return dependency

def require_all_roles(*required_roles):

    def dependency(user=Depends(get_current_user)):

        user_role = getattr(user["role"], "value", user["role"])

        permissions = ROLE_HIERARCHY.get(user_role, {user_role})

        if not all(role in permissions for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden"
            )

        return user

    return dependency


#RBAC
def require_role(*allowed_roles):

    def dependency(
        user=Depends(get_current_user)
    ):  
        
        role = user.role.name
        permissions = ROLE_HIERARCHY.get(role, {role})

        if not any (role in permissions for role in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: insufficient permissions"
            )

        return user

    return dependency

