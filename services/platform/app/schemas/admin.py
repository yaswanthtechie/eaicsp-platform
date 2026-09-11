from datetime import datetime

from pydantic import BaseModel, ConfigDict
from app.schemas.user import RoleChangeHistoryResponse
class AuditLogResponse(BaseModel):
    id: int
    user_id: int | None
    event_type: str
    email: str | None
    ip_address: str | None
    details: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ============================================================
# SECURITY DASHBOARD RESPONSE SCHEMAS
# ============================================================
class FailedLoginTrendResponse(BaseModel):
    last_24_hours: int
    last_7_days: int

class ActiveSessionResponse(BaseModel):
    session_id: int
    user_id: int
    email: str
    created_at: str
    expires_at: str

class SecurityDashboardResponse(BaseModel):
    failed_login_trends: FailedLoginTrendResponse
    currently_active_sessions: int
    active_sessions: list[ActiveSessionResponse]
    recent_role_changes: list[RoleChangeHistoryResponse]
    lockout_events: list[AuditLogResponse]

class ServiceAPIKeyCreateRequest(BaseModel):
    service_name: str
    expires_at: datetime | None = None

class ServiceAPIKeyCreateResponse(BaseModel):
    id: int
    service_name: str
    api_key: str
    expires_at: datetime | None = None
    is_active: bool

class ServiceAPIKeyResponse(BaseModel):
    id: int
    service_name: str
    expires_at: datetime | None = None
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None = None

