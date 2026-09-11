
from fastapi import Depends,HTTPException, Header,status
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.service_api_keys import ServiceAPIKey
from app.database import get_db

import hashlib
import secrets

def generate_service_api_key() -> str:
    return "sk_" + secrets.token_urlsafe(32)

def hash_service_api_key(api_key: str) -> str:
    return hashlib.sha256(
        api_key.encode("utf-8")
    ).hexdigest()

def verify_service_api_key(
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing service API key",
        )

    key_hash = hash_service_api_key(x_api_key)

    service_key = (
        db.query(ServiceAPIKey)
        .filter(
            ServiceAPIKey.key_hash == key_hash,
            ServiceAPIKey.is_active.is_(True),
        )
        .first()
    )

    if service_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service API key",
        )

    now = datetime.now(timezone.utc)

    if service_key.expires_at is not None:
        expires_at = service_key.expires_at

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at <= now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Service API key expired",
            )

    service_key.last_used_at = now
    db.commit()

    return {
        "service": service_key.service_name,
        "auth_type": "api_key",
    }