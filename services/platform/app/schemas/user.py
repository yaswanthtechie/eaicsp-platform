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
    role: Role
    is_active: bool


