from sqlalchemy import Column,Integer,String
from app.database import Base
from sqlalchemy.orm import relationship

class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name=Column(String(50),unique=True,nullable=False,index=True)
    description=Column(String(255),nullable=True)
    users = relationship(
            "User",
            back_populates="role"
        )
