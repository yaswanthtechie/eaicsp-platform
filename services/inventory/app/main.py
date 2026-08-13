from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, engine
from app.routes.inventory import router as inventory_router

# Import all models so SQLAlchemy knows about
# Inventory and SalesHistory tables.
import app.models


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)

    yield

    # Shutdown
    engine.dispose()


app = FastAPI(
    title="Inventory Service",
    version="1.0.0",
    lifespan=lifespan,
)


app.include_router(
    inventory_router,
    prefix="/api/v1/inventory",
    tags=["Inventory"],
)