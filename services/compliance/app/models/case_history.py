from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)

from app.core.database import Base


class CaseHistory(Base):

    __tablename__ = "case_history"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    case_id = Column(
        Integer,
        ForeignKey(
            "compliance_case.id"
        ),
        nullable=False,
        index=True,
    )

    from_status = Column(
        String,
        nullable=True,
    )

    to_status = Column(
        String,
        nullable=False,
    )

    changed_by = Column(
        String,
        nullable=True,
    )

    reason = Column(
        Text,
        nullable=True,
    )

    comments = Column(
        Text,
        nullable=True,
    )

    changed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )