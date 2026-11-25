from datetime import UTC, datetime

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import DATABASE_URL

# Use SQLite-specific connection options only for SQLite databases.
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_now(db: Session) -> datetime:
    """Return the current timestamp from the central database clock as a UTC datetime.

    Guarantees a consistent, monotonic clock source across multiple Platform Service
    instances, eliminating reliance on synchronized physical host clocks.
    """
    ts = db.scalar(select(func.now()))
    if ts is None:
        return datetime.now(UTC)
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)
