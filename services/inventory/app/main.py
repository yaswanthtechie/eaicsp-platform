from fastapi import FastAPI

from app.routes.inventory import router as inventory_router
from app.database import Base, engine


import app.models

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Inventory Service",
    version="1.0.0"
)

app.include_router(
    inventory_router,
    prefix="/api/v1/inventory",
    tags=["Inventory"]
)


