from pydantic import BaseModel

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
    token_type: str