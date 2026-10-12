from sqlalchemy import Boolean, Column, Integer, String

from app.core.database import Base


class RegulatoryRule(Base):
    __tablename__ = "regulatory_rules"

    id = Column(Integer, primary_key=True, index=True)
    rule_code = Column(String(100), unique=True, nullable=False, index=True)
    country = Column(String(100), nullable=False, index=True)
    rule_name = Column(String(255), nullable=False)
    description = Column(String(500), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)