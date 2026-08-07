from fastapi import FastAPI

from app.database import Base, engine
from app.routes.inventory import router as inventory_router
import app.models

app = FastAPI(
    title="Inventory Service",
    version="1.0.0",
)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


app.include_router(
    inventory_router,
    prefix="/api/v1/inventory",
    tags=["Inventory"],
)