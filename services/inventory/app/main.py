from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import (
    Base,
    engine,
)

from app.routes.inventory import (
    router as inventory_router,
)

import app.models


@asynccontextmanager
async def lifespan(app: FastAPI):

    Base.metadata.create_all(
        bind=engine
    )

    yield

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