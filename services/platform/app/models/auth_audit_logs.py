from sqlalchemy import Column, DateTime, ForeignKey, Integer, String,Text
from sqlalchemy.sql import func

from app.database import Base

class AuthAuditLog(Base):
    __tablename__ = "auth_audit_logs"

    id = Column(Integer,primary_key=True,index=True)
    user_id = Column(Integer,ForeignKey("users.id"),nullable=True,index=True )
    event_type = Column(String(50),nullable=False,index=True)
    email = Column(String(255),nullable=True,index=True )
    ip_address = Column(String(100),nullable=True)
    details = Column(Text,nullable=True)
    created_at = Column(DateTime(timezone=True),server_default=func.now(),nullable=False)
