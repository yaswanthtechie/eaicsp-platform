import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app import models as _models  # noqa: F401 - registers every table on Base
from app.core.logging_config import configure_logging
from app.database import Base, engine
from app.middleware.logging import log_requests
from app.routes.admin_routes import router as admin_router
from app.routes.auth_routes import router as auth_router
from app.routes.user_routes import router as user_router

# Ensure scripts package is resolvable regardless of working directory
_platform_dir = Path(__file__).resolve().parent.parent
if str(_platform_dir) not in sys.path:
    sys.path.insert(0, str(_platform_dir))

from scripts.migrate_add_user_uuid import run_migration  # noqa: E402

logger = logging.getLogger(__name__)

configure_logging()


def init_db(target_engine=None):
    """Initialize database schema and execute pending migrations.

    Ensures all tables exist and required column migrations (such as user_uuid)
    are applied before requests can access the database.
    """
    if target_engine is None:
        target_engine = engine
    Base.metadata.create_all(bind=target_engine)
    run_migration(target_engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager.

    Executes schema initialization and migrations before accepting traffic.
    Fails startup with an explicit error if migrations fail.
    """
    try:
        init_db(engine)
    except Exception as exc:
        logger.error(
            "Platform Service startup failed during database initialization: %s", exc
        )
        raise RuntimeError(
            f"Platform Service database migration failed: {exc}"
        ) from exc
    yield


app = FastAPI(lifespan=lifespan)

app.middleware("http")(log_requests)

app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(user_router)


@app.get("/")
def root():
    return {"message": "Platform Service is running"}


@app.get("/health")
def health():
    return {"status": "healthy", "service": "platform"}
