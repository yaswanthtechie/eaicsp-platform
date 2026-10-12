from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
)

from app.database import Base


class Outbox(Base):
    __tablename__ = "outbox"

    id = Column(
        String,
        primary_key=True,
        default=lambda: uuid4().hex,
    )

    event_type = Column(
        String,
        nullable=False,
        index=True,
    )

    aggregate_type = Column(
        String,
        nullable=False,
    )

    aggregate_id = Column(
        String,
        nullable=False,
        index=True,
    )

    payload = Column(
        Text,
        nullable=False,
    )

    status = Column(
        String,
        nullable=False,
        default="PENDING",
        index=True,
    )

    retry_count = Column(
        Integer,
        nullable=False,
        default=0,
    )

    last_error = Column(
        Text,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )

    published_at = Column(
        DateTime,
        nullable=True,
    )
