from fastapi import APIRouter, Depends, HTTPException, status,Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timezone,timedelta
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
from app.schemas.admin import(
    AuditLogResponse, 
    SecurityDashboardResponse,
    ServiceAPIKeyResponse,
    ServiceAPIKeyCreateRequest,
    ServiceAPIKeyCreateResponse
)
from app.models.service_api_keys import ServiceAPIKey
from app.models.auth_audit_logs import AuthAuditLog
from app.services.audit_service import (
    create_audit_log,
    TOKEN_REVOKED,
    ROLE_CHANGED,
    LOGIN_FAILED,
    ACCOUNT_LOCKED
)
from app.models.refresh_token import RefreshToken
from app.schemas.auth import SessionResponse
from app.core.dependencies import require_role,get_current_user,require_any_role
from app.core.password_validator import validate_password
from app.core.security import hash_password
from app.core.service_auth import (
    generate_service_api_key,
    hash_service_api_key,
)
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

    # Deactivate account
    user.is_active = False

    # Revoke all active refresh tokens/sessions
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
        .filter(RoleChangeHistory.user_id == user_id)
        .order_by(
            RoleChangeHistory.changed_at.desc(),
            RoleChangeHistory.id.desc(),
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

    '''validate_password(request.new_password)
    user.password = hash_password(
        request.new_password
    )'''
    validate_password(request.new_password)

    user.password = hash_password(
        request.new_password
    )

    now = datetime.now(timezone.utc)

    user.password_changed_at = now
    user.password_expires_at = (
        now + timedelta(days=90)
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

# ============================================================
# SECURITY DASHBOARD
# ============================================================

@router.get(
    "/security-dashboard",
    response_model=SecurityDashboardResponse,
)
def security_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # --------------------------------------------------------
    # ADMIN ACCESS CHECK
    # --------------------------------------------------------
    if (
        not current_user.role
        or current_user.role.name not in {
            "ceo",
            "vp_operations",
        }
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    now = datetime.now(timezone.utc)

    last_24_hours = now - timedelta(hours=24)
    last_7_days = now - timedelta(days=7)

    # --------------------------------------------------------
    # 1. FAILED LOGIN TRENDS
    # --------------------------------------------------------
    failed_login_24h = (
        db.query(AuthAuditLog)
        .filter(
            AuthAuditLog.event_type == "LOGIN_FAILED",
            AuthAuditLog.created_at >= last_24_hours,
        )
        .count()
    )

    failed_login_7d = (
        db.query(AuthAuditLog)
        .filter(
            AuthAuditLog.event_type == "LOGIN_FAILED",
            AuthAuditLog.created_at >= last_7_days,
        )
        .count()
    )

    failed_login_trends = {
        "last_24_hours": failed_login_24h,
        "last_7_days": failed_login_7d,
    }

    # --------------------------------------------------------
    # 2. CURRENTLY ACTIVE SESSIONS
    # --------------------------------------------------------
    active_sessions = (
        db.query(
            RefreshToken,
            User.email,
        )
        .join(
            User,
            User.id == RefreshToken.user_id,
        )
        .filter(
            RefreshToken.is_revoked.is_(False),
            RefreshToken.expires_at > now,
            User.is_active.is_(True),
        )
        .order_by(
            RefreshToken.created_at.desc()
        )
        .all()
    )

    active_session_data = [
        {
            "session_id": session.id,
            "user_id": session.user_id,
            "email": email,
            "created_at": session.created_at.isoformat(),
            "expires_at": session.expires_at.isoformat(),
        }
        for session, email in active_sessions
    ]

    # --------------------------------------------------------
    # 3. RECENT ROLE CHANGES
    # --------------------------------------------------------
    role_changes = (
        db.query(RoleChangeHistory)
        .order_by(
            RoleChangeHistory.changed_at.desc(),
            RoleChangeHistory.id.desc(),
        )
        .limit(20)
        .all()
    )

    role_change_data = [
        {
            "id": item.id,
            "user_id": item.user_id,
            "old_role": item.old_role,
            "new_role": item.new_role,
            "changed_by": item.changed_by,
            "changed_at": item.changed_at.isoformat(),
        }
        for item in role_changes
    ]

    # --------------------------------------------------------
    # 4. LOCKOUT EVENTS
    # --------------------------------------------------------
    lockout_events = (
        db.query(AuthAuditLog)
        .filter(
            AuthAuditLog.event_type == "ACCOUNT_LOCKED"
        )
        .order_by(
            AuthAuditLog.created_at.desc()
        )
        .limit(20)
        .all()
    )

    # --------------------------------------------------------
    # FINAL DASHBOARD RESPONSE
    # --------------------------------------------------------
    return {
        "failed_login_trends": failed_login_trends,

        "currently_active_sessions": len(
            active_session_data
        ),

        "active_sessions": active_session_data,

        "recent_role_changes": role_change_data,

        "lockout_events": lockout_events,
    }

# ============================================================
# ISSUE SERVICE API KEY
# ============================================================

@router.post(
    "/service-keys",
    response_model=ServiceAPIKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_service_api_key(
    request: ServiceAPIKeyCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_any_role("ceo", "vp_operations")
    ),
):
    # Generate raw API key
    api_key = generate_service_api_key()

    # Hash before storing
    key_hash = hash_service_api_key(api_key)

    service_key = ServiceAPIKey(
    service_name=request.service_name,
    key_hash=key_hash,
    is_active=True,
    expires_at=request.expires_at,
    created_by=current_user.id,
   )
    db.add(service_key)
    db.commit()
    db.refresh(service_key)

    return {
        "id": service_key.id,
        "service_name": service_key.service_name,
        "api_key": api_key,
        "expires_at": service_key.expires_at,
        "is_active": service_key.is_active,
    }

# ============================================================
# LIST SERVICE API KEYS
# ============================================================

@router.get(
    "/service-keys",
    response_model=list[ServiceAPIKeyResponse],
)
def list_service_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_any_role("ceo", "vp_operations")
    ),
):
    service_keys = (
        db.query(ServiceAPIKey)
        .order_by(ServiceAPIKey.created_at.desc())
        .all()
    )

    return [
        {
            "id": key.id,
            "service_name": key.service_name,
            "expires_at": key.expires_at,
            "is_active": key.is_active,
            "created_at": key.created_at,
            "last_used_at": key.last_used_at,
        }
        for key in service_keys
    ]

# ============================================================
# REVOKE SERVICE API KEY
# ============================================================

@router.delete(
    "/service-keys/{key_id}"
)
def revoke_service_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_any_role("ceo", "vp_operations")
    ),
):
    service_key = (
        db.query(ServiceAPIKey)
        .filter(ServiceAPIKey.id == key_id)
        .first()
    )

    if service_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service API key not found",
        )

    if not service_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Service API key already revoked",
        )

    service_key.is_active = False

    create_audit_log(
        db=db,
        event_type=TOKEN_REVOKED,
        user_id=current_user.id,
        details=(
            f"Service API key {key_id} "
            f"for {service_key.service_name} "
            f"revoked by admin {current_user.id}"
        ),
    )

    db.commit()

    return {
        "message": "Service API key revoked successfully",
        "key_id": key_id,
    }
