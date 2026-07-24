from fastapi import FastAPI

from app.routes.auth_routes import router as auth_router
from app.routes.user_routes import router as user_router
from app.routes.admin_routes import router as admin_router

app = FastAPI()

app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(user_router)

@app.get("/")
def root():
    return {
        "message": "Platform Service is running"
    }