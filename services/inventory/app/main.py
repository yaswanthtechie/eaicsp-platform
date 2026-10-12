import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.database import engine
import app.models

from app.routes.purchase_orders import (
    router as purchase_order_router,
)
from app.routes.reports import (
    router as reports_router,
)
from app.routes.inventory import (
    router as inventory_router,
)
from app.services.outbox_relay import run_relay_worker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # NOTE: Manual Base.metadata.create_all() has been removed per specification.
    # All database schemas are managed strictly via Alembic migrations.

    # Start Outbox Relay background worker if enabled
    stop_relay_event = threading.Event()
    relay_thread = None

    if getattr(settings, "ENABLE_OUTBOX_RELAY", True):
        logger.info("Initializing background Outbox Relay worker thread...")
        relay_thread = threading.Thread(
            target=run_relay_worker,
            kwargs={
                "poll_interval": getattr(settings, "OUTBOX_RELAY_INTERVAL_SECONDS", 2.0),
                "stop_event": stop_relay_event,
            },
            daemon=True,
            name="outbox-relay-worker",
        )
        relay_thread.start()

    yield

    if stop_relay_event and relay_thread:
        stop_relay_event.set()
        relay_thread.join(timeout=3.0)

    engine.dispose()


app = FastAPI(
    title="Inventory Service",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["Health"])
def health_check():
    """Healthcheck endpoint for Docker and orchestration probes."""
    return {"status": "ok", "service": "inventory-service"}


# Specific routers must be registered before
# the inventory catch-all routes.
app.include_router(
    purchase_order_router,
)

app.include_router(
    reports_router,
    prefix="/api/v1/inventory",
)

app.include_router(
    inventory_router,
    prefix="/api/v1/inventory",
    tags=["Inventory"],
)