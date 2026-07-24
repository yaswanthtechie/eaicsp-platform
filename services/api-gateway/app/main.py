from fastapi import FastAPI
import httpx
from contextlib import asynccontextmanager
from app.core.config import settings
from app.routes import health, gateway
from app.schemas.responses import RootResponse
from app.middleware.logging import LoggingMiddleware
from app.middleware.ratelimit import (
    limiter,
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
    SlowAPIMiddleware,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(timeout=settings.TIMEOUT_SECONDS)
    yield
    await app.state.http_client.aclose()

app = FastAPI(
    title=settings.APP_NAME,
    openapi_url="/api/v1/openapi.json",
    description="API Gateway for the platform",
    version=settings.VERSION,
    lifespan=lifespan,
)

# Apply rate limiting globally
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
)

# Add middlewares
app.add_middleware(LoggingMiddleware)
app.add_middleware(SlowAPIMiddleware)

# Health router
app.include_router(
    health.router,
    prefix="/health",
    tags=["health"],
)

# Root endpoint
@app.get("/", tags=["Root"], response_model=RootResponse)
async def root():
    return {
        "message": "API Gateway is running",
        "status": "healthy",
        "version": settings.VERSION,
    }

# Gateway router (keep last because of catch-all route)
app.include_router(gateway.router)