from fastapi import APIRouter, Depends, HTTPException, status,Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timezone

from app.database import get_db

from app.models.users import User
from app.models.roles import Role as RoleModel
from app.models.role_change_history import RoleChangeHistory

from app.schemas.user import (
    AdminCreateUserRequest,
    RoleChangeRequest,
    RoleChangeHistoryResponse,
    ForceResetPasswordRequest,
    UserResponse,

)
from app.schemas.admin import AuditLogResponse
from app.models.auth_audit_logs import AuthAuditLog
from app.services.audit_service import (
    create_audit_log,
    TOKEN_REVOKED,
    ROLE_CHANGED
)
from app.models.refresh_token import RefreshToken
from app.schemas.auth import SessionResponse
from app.core.dependencies import require_role,get_current_user,require_any_role
from app.core.password_validator import validate_password
from app.core.security import hash_password

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin"]
)

class AdminTestResponse(BaseModel):
    message:str
    user:UserResponse

@router.get(
    "/test",
    response_model=AdminTestResponse
)

def admin_test(user=Depends(require_role("ceo","vp_operations"))):
    return {
        "message": "Admin access granted",
        "user": {
            "user_id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.name if user.role else None,
            "is_active": user.is_active,
        }
    }

# ============================================================
# LIST USERS
# ============================================================

@router.get(
    "/users",
    response_model=list[UserResponse]
)
def list_users(
    db: Session = Depends(get_db),
    current_user=Depends(
        require_any_role("ceo", "vp_operations")
    )
):
    users = (
        db.query(User)
        .order_by(User.id)
        .all()
    )

    return [
        {
            "user_id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.name if user.role else None,
            "is_active": user.is_active,
        }
        for user in users
    ]

# ============================================================
# CREATE USER
# ============================================================

@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def create_user(
    request: AdminCreateUserRequest,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_any_role("ceo", "vp_operations")
    )
):
    email = request.email.lower()
    
    existing = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists"
        )

    validate_password(request.password)
    role_id = None
    role_name = None
    if request.role is not None:

        role = (
            db.query(RoleModel)
            .filter(
                RoleModel.name == request.role.value
            )
            .first()
        )

        if role is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role"
            )

        role_id = role.id
        role_name = role.name

    user = User(
        email=email,
        full_name=request.full_name,
        password=hash_password(request.password),
        role_id=role_id,
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)


    if role_name is not None:

        history = RoleChangeHistory(
            user_id=user.id,
            old_role=None,
            new_role=role_name,
            changed_by=current_user.id,
        )

        db.add(history)
        db.commit()

    return {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.name if user.role else None,
        "is_active": user.is_active,
    }

# ============================================================
# DEACTIVATE USER
# ============================================================

@router.patch(
    "/users/{user_id}/deactivate",
    response_model=UserResponse
)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_any_role("ceo", "vp_operations")
    )
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account"
        )
    user.is_active = False

    db.commit()
    db.refresh(user)

    return {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.name if user.role else None,
        "is_active": user.is_active,
    }


# ============================================================
# ASSIGN ROLE
# ============================================================

@router.patch(
    "/users/{user_id}/role",
    response_model=UserResponse
)
def change_user_role(
    user_id: int,
    request: RoleChangeRequest,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_any_role("ceo", "vp_operations")
    )
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    new_role = (
        db.query(RoleModel)
        .filter(
            RoleModel.name == request.role.value
        )
        .first()
    )

    if new_role is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role"
        )

    old_role = (
        user.role.name
        if user.role
        else None
    )

    if old_role == new_role.name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has this role"
        )

    user.role_id = new_role.id

    history = RoleChangeHistory(
        user_id=user.id,
        old_role=old_role,
        new_role=new_role.name,
        changed_by=current_user.id,
    )

    db.add(history)
    create_audit_log(
        db=db,
        event_type=ROLE_CHANGED,
        user_id=user.id,
        email=user.email,
        details=(
            f"Role changed from {old_role} "
            f"to {new_role.name} "
            f"by user {current_user.id}"
        ),
    )
    db.commit()
    db.refresh(user)

    return {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.name if user.role else None,
        "is_active": user.is_active,
    }

# ============================================================
# ROLE CHANGE HISTORY
# ============================================================

@router.get(
    "/users/{user_id}/role-history",
    response_model=list[RoleChangeHistoryResponse]
)
def role_change_history(
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_any_role("ceo", "vp_operations")
    )
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    history = (
        db.query(RoleChangeHistory)
        .filter(
            RoleChangeHistory.user_id == user_id
        )
        .order_by(
            RoleChangeHistory.changed_at.desc()
        )
        .all()
    )

    return [
        {
            "id": item.id,
            "user_id": item.user_id,
            "old_role": item.old_role,
            "new_role": item.new_role,
            "changed_by": item.changed_by,
            "changed_at": item.changed_at.isoformat(),
        }
        for item in history
    ]



# ============================================================
# FORCE RESET PASSWORD
# ============================================================

@router.post(
    "/users/{user_id}/force-reset-password"
)
def force_reset_password(
    user_id: int,
    request: ForceResetPasswordRequest,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_any_role("ceo", "vp_operations")
    )
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    validate_password(request.new_password)
    user.password = hash_password(
        request.new_password
    )

# Revoke all active sessions after force password reset
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.is_revoked.is_(False),
    ).update(
    {
            RefreshToken.is_revoked: True
    },
    synchronize_session=False,
)
    
    db.commit()

    return {
        "message": "Password reset successfully"
}

# ============================================================
# ACTIVE SESSIONS
# ============================================================
@router.get(
    "/users/{user_id}/sessions",
    response_model=list[SessionResponse]
)
def list_user_sessions(
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_any_role("ceo", "vp_operations")
    )
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    now = datetime.now(timezone.utc)

    sessions = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False,
            RefreshToken.expires_at > now
        )
        .order_by(
            RefreshToken.created_at.desc()
        )
        .all()
    )

    return [
        {
            "id": session.id,
            "user_id": session.user_id,
            "created_at": session.created_at.isoformat(),
            "expires_at": session.expires_at.isoformat(),
            "is_revoked": session.is_revoked,
        }
        for session in sessions
    ]

# ============================================================
# REVOKE SESSION
# ============================================================
@router.delete(
    "/users/{user_id}/sessions/{session_id}"
)
def revoke_user_session(
    user_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_any_role("ceo", "vp_operations")
    )
):
    session = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.id == session_id,
            RefreshToken.user_id == user_id
        )
        .first()
    )

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    if session.is_revoked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session already revoked"
        )

    session.is_revoked = True
    create_audit_log(
        db=db,
        event_type=TOKEN_REVOKED,
        user_id=user_id,
        details=(
            f"Session {session_id} revoked "
            f"by user {current_user.id}"
        ),
    )

    db.commit()

    return {
        "message": "Session revoked successfully"
    }


# ============================================================
# AUDIT LOGS
# ============================================================
@router.get(
    "/audit-logs",
    response_model=list[AuditLogResponse],
)
def get_audit_logs(
    user_id: int | None = Query(default=None),
    event_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(
        require_any_role("ceo", "vp_operations")
    ),
):
    query = db.query(AuthAuditLog)

    if user_id is not None:
        query = query.filter(
            AuthAuditLog.user_id == user_id
        )

    if event_type is not None:
        query = query.filter(
            AuthAuditLog.event_type == event_type
        )

    return (
        query
        .order_by(AuthAuditLog.created_at.desc())
        .limit(500)
        .all()
    )

