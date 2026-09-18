from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
)
from sqlalchemy.sql import func

from app.database import Base

class ServiceAPIKey(Base):
    __tablename__ = "service_api_keys"

    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String(100),nullable=False,index=True)
    key_hash = Column(String(255),nullable=False,unique=True,index=True)
    is_active = Column(Boolean,default=True,nullable=False)
    created_at = Column(DateTime(timezone=True),server_default=func.now(),nullable=False)
    expires_at = Column(DateTime(timezone=True),nullable=True)
    last_used_at = Column(DateTime(timezone=True),nullable=True)
    created_by = Column(Integer,ForeignKey("users.id"),nullable=True)