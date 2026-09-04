from fastapi import FastAPI

from app.routes.auth_routes import router as auth_router
from app.routes.user_routes import router as user_router
from app.routes.admin_routes import router as admin_router
from app.database import Base, engine
from app.models.users import User
from app.models.roles import Role
from app.models.refresh_token import RefreshToken
from app.models.failed_login_attempts import FailedLoginAttempt
from app.models.role_change_history import RoleChangeHistory
from app.models.auth_audit_logs import AuthAuditLog
from app.models.password_reset_tokens import PasswordResetToken


app = FastAPI()

app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(user_router)

# Create tables
Base.metadata.create_all(bind=engine)

@app.get("/")
def root():
    return {
        "message": "Platform Service is running"
    }
