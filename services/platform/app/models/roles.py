from sqlalchemy import Column,Integer,String
from app.database import Base

class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name=Column(Integer,unique=True,nullable=False,index=True)
    description=Column(String(255),nullable=True)