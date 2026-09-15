from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, String
from app.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class FailedLoginAttempt(Base):
    __tablename__ = "failed_login_attempts"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, index=True)
    ip_address = Column(String(100), nullable=False)
    attempted_at = Column(
        DateTime(timezone=True),
        default=utc_now
    )
