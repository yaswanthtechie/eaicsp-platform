from sqlalchemy import create_engine
from config import (
    DB_HOST,
    DB_PORT,
    DB_NAME,
    DB_USER,
    DB_PASSWORD,
)

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

_engine = None


def get_engine():
    """Builds the SQLAlchemy engine lazily, on first use, instead of at
    import time. Importing this module (directly or transitively, e.g. via
    logger/watermark/alert_service) should never have side effects - it
    should just define how to get an engine, not build one. This matters
    most for Airflow: the scheduler imports every DAG file to parse it, and
    that must stay cheap and side-effect-free."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            future=True,
        )
    return _engine
