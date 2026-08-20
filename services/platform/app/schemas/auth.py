from pydantic import BaseModel,EmailStr

class RegisterRequest(BaseModel):
    full_name:str
    email:EmailStr
    password:str

class LoginRequest(BaseModel):
    username: str
    password: str

class LogoutRequest(BaseModel):
    refresh_token: str
    
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class RefreshRequest(BaseModel):
    refresh_token: str

class AccessTokenResponse(BaseModel):
    access_token: str
    refreh_token:str
    token_type: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

class SessionResponse(BaseModel):
    id: int
    user_id: int
    created_at: str
    expires_at: str
    is_revoked: bool
