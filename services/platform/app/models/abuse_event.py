from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, String, Text
from app.database import Base

class AbuseEvent(Base):
    __tablename__ = "abuse_events"

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String(100), nullable=False, index=True)
    endpoint = Column(String(255), nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    request_count = Column(Integer, nullable=False, default=0)
    detected_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    details = Column(Text, nullable=True)