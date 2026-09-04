from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.database import Base


class RoleChangeHistory(Base):
    __tablename__ = "role_change_history"

    id = Column(Integer,primary_key=True,index=True)
    user_id = Column(Integer,ForeignKey("users.id"),nullable=False,index=True)
    old_role = Column(String(50),nullable=True)
    new_role = Column(String(50),nullable=False)
    changed_by = Column(Integer,ForeignKey("users.id"),nullable=False)
    changed_at = Column(DateTime(timezone=True),server_default=func.now(),nullable=False)

