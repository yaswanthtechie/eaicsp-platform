from sqlalchemy import Column,ForeignKey,Boolean,Integer,String 
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.roles import Role

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255),unique=True, nullable=False, index=True)
    full_name=Column(String(255),nullable=False)
    password=Column(String(255),nullable=False)
    is_active=Column(Boolean, default=True, nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"),nullable=True)
    role = relationship("Role",back_populates="users")

