import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    REFRESH_TOKEN_EXPIRE_DAYS,
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


def hash_token(token: str) -> str:
    """Return SHA-256 hex digest of the given token.

    If the token is already a 64-char hex digest (without JWT dots), return as is.
    """
    if len(token) == 64 and "." not in token:
        try:
            int(token, 16)
            return token
        except ValueError:
            pass
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(data: dict, expires_delta=None):
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "type": "access"})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict, family_id: str | None = None):
    to_encode = data.copy()

    fam_id = family_id or to_encode.get("family_id") or str(uuid.uuid4())
    to_encode.update(
        {
            "type": "refresh",
            "jti": str(uuid.uuid4()),
            "family_id": fam_id,
            "exp": datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        }
    )

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str):
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
