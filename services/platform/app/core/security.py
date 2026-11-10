import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    SECRET_KEY,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)


def build_access_claims(user: Any, role_name: str | None = None) -> dict[str, Any]:
    """Build standard JWT access token claims for a user.

    Ensures sub, user_id, role, and user_uuid are consistently populated across
    all token issuance flows (login, MFA verification, refresh, and SSO).
    """
    role = (
        role_name
        if role_name is not None
        else (user.role.name if getattr(user, "role", None) else None)
    )
    claims: dict[str, Any] = {
        "sub": user.email,
        "user_id": user.id,
        "role": role,
    }
    user_uuid = getattr(user, "user_uuid", None)
    if user_uuid is not None:
        claims["user_uuid"] = str(user_uuid)
    return claims


def create_access_token(data: dict, expires_delta=None):
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "type": "access"})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict):
    to_encode = data.copy()

    to_encode.update(
        {
            "type": "refresh",
            "jti": str(uuid.uuid4()),
            "exp": datetime.now(UTC) + timedelta(days=7),
        }
    )

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str):
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
