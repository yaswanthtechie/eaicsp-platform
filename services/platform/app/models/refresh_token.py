from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from app.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class RefreshToken(Base):
    __tablename__ = "refresh_token"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer,nullable=False, index=True)
    token = Column(String(512), unique=True, nullable=False, index=True)
    is_revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    expires_at = Column(DateTime(timezone=True), nullable=False)
