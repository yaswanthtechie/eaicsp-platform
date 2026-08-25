from pydantic import BaseModel, EmailStr
from enum import Enum

class Role(str, Enum):
    ceo = "ceo"
    vp_operations = "vp_operations"
    procurement_manager = "procurement_manager"
    logistics_manager = "logistics_manager"
    compliance_officer = "compliance_officer"
    warehouse_manager = "warehouse_manager"
    analyst = "analyst"
    supplier = "supplier"
    
class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str

class UserResponse(BaseModel):
    user_id: int
    email: EmailStr
    full_name: str
    role: Role | None
    is_active: bool

class AdminCreateUserRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: Role | None 

class RoleChangeRequest(BaseModel):
    role: Role

class ForceResetPasswordRequest(BaseModel):
    new_password: str

class RoleChangeHistoryResponse(BaseModel):
    id: int
    user_id: int
    old_role: str | None
    new_role: str
    changed_by: int
    changed_at: str

