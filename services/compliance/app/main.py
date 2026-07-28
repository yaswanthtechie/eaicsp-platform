from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.routes.compliance import router
from app.services.sanctions_service import load_csv

@asynccontextmanager
async def lifespan(app: FastAPI):

    load_csv()

    yield

app = FastAPI(

    title="Compliance Service",

    version="1.0.0",

    lifespan=lifespan

)

app.include_router(

    router,

    prefix="/api/v1/compliance",

    tags=["Compliance"]

)
@app.get("/")
def home():

    return {

        "message":
        "Compliance Service running"

    }