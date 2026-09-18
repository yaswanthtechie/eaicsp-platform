from fastapi import APIRouter, Form, HTTPException
from pydantic import BaseModel
from secrets import token_urlsafe

router = APIRouter(prefix="/auth")


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


@router.post("/login")
def login(
    username: str = Form(...),
    password: str = Form(...),
):
    # Demo authentication:
    # Any non-empty username and password are accepted.
    if not username.strip() or not password.strip():
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    return {
        "access_token": token_urlsafe(32),
        "refresh_token": token_urlsafe(32),
        "token_type": "bearer",
        "supplier_id": "SUP001",
    }


@router.post("/refresh")
def refresh_token(request: RefreshTokenRequest):
    if not request.refresh_token.strip():
        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token",
        )

    return {
        "access_token": token_urlsafe(32),
        "refresh_token": token_urlsafe(32),
        "token_type": "bearer",
    }


@router.post("/logout")
def logout(request: LogoutRequest):
    return {
        "message": "Logged out successfully"
    }
