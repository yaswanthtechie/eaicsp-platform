from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.routes.compliance import router as compliance_router
from app.services.sanctions_service import load_all_sanctions


@asynccontextmanager
async def lifespan(app: FastAPI):

    print("Loading sanctions index...")
    load_all_sanctions()

    yield


app = FastAPI(
    title="Compliance Service",
    version="0.1.0",
    lifespan=lifespan
)


app.include_router(
    compliance_router,
    prefix="/api/v1/compliance",
    tags=["Compliance"]
)

@app.get("/")
def home():
    return {
        "service": "Compliance Service",
        "status": "running",
        "version": "0.1.0"
    }