from fastapi import FastAPI

from app import models as _models  # noqa: F401 - registers every table on Base
from app.core.logging_config import configure_logging
from app.database import Base, engine
from app.middleware.logging import log_requests
from app.routes.admin_routes import router as admin_router
from app.routes.auth_routes import router as auth_router
from app.routes.user_routes import router as user_router

configure_logging()

app = FastAPI()

app.middleware("http")(log_requests)

app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(user_router)

# Create tables
Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return {"message": "Platform Service is running"}


@app.get("/health")
def health():
    return {"status": "healthy", "service": "platform"}
