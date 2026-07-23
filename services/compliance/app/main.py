from fastapi import FastAPI

from app.routes.compliance import router
from app.services.sanctions_service import load_csv

app = FastAPI(title="Compliance Service")


@app.on_event("startup")
def startup():
    load_csv()


@app.get("/")
def home():
    return {"message": "Compliance Service Running"}


app.include_router(
    router,
    prefix="/api/v1/compliance",
    tags=["Compliance"]
)

