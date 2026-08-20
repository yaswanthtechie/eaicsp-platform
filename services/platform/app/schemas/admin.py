'''
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str


class AdminUserResponse(BaseModel):
    id: int
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ForceResetPasswordRequest(BaseModel):
    new_password: str

class RoleChangeRequest(BaseModel):
    new_role: str


class SessionResponse(BaseModel):
    id: int
    user_id: int
    created_at: datetime
    expires_at: datetime
    is_revoked: bool

    model_config = ConfigDict(from_attributes=True)


class RoleHistoryResponse(BaseModel):
    id: int
    user_id: int
    old_role: str
    new_role: str
    changed_by: int
    ip_address: str | None
    changed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogResponse(BaseModel):
    id: int
    user_id: int | None
    event_type: str
    ip_address: str | None
    details: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

'''
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    id: int
    user_id: int | None
    event_type: str
    email: str | None
    ip_address: str | None
    details: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)