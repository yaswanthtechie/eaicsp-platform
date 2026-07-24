from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.services.auth_service import login
from app.core.security import (
    create_access_token,
    create_refresh_token
)

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"]
)

login_attempts = {}

MAX_ATTEMPTS = 5
WINDOW = timedelta(minutes=15)

@router.post("/login")
def login_user(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends()
):

    client_ip = request.client.host
    now = datetime.utcnow()

    attempts = login_attempts.get(client_ip, [])
    attempts = [
        t for t in attempts
        if now - t < WINDOW
    ]

    if len(attempts) >= MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again after 15 minutes."
        )

  
    user = login(
        form_data.username,
        form_data.password
    )


    if not user:
        attempts.append(now)
        login_attempts[client_ip] = attempts

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    login_attempts.pop(client_ip, None)

    access_token = create_access_token(
        {
            "sub": user["email"],
            "role": user["role"],
            "user_id": user["user_id"],
          
        }
    )

    refresh_token = create_refresh_token(
        {
            "sub": user["email"],
            "user_id": user["user_id"]
        }
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }