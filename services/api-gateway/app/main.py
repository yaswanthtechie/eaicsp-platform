<<<<<<< HEAD
import sys
from pathlib import Path
# Add the parent directory (eaicsp-platform) to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # pyright: ignore [missing-import]
# pyrefly: ignore [missing-import]
from fastapi import FastAPI
import httpx  # pyright: ignore [missing-import]
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
=======
"""
Main FastAPI application for the API Gateway.
"""

import httpx
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.middleware.logging import LoggingMiddleware
from app.middleware.ratelimit import (
    RateLimitExceeded,
    SlowAPIMiddleware,
    _rate_limit_exceeded_handler,
    limiter,
)
from app.routes import gateway, health
from app.schemas.responses import RootResponse


# --------------------------------------------------
# Application Lifespan
# --------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialize and clean up application resources.
    """

    app.state.http_client = httpx.AsyncClient(
        timeout=settings.TIMEOUT_SECONDS
    )

    try:
        yield
    finally:
        await app.state.http_client.aclose()


# --------------------------------------------------
# FastAPI Application
# --------------------------------------------------

app = FastAPI(
    title=settings.APP_NAME,
    description="API Gateway for the platform",
    version=settings.VERSION,
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

# --------------------------------------------------
# Global Rate Limiter
# --------------------------------------------------

app.state.limiter = limiter

>>>>>>> mahendher/round3-api-gateway
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
)

<<<<<<< HEAD
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
=======
# --------------------------------------------------
# Middlewares
# --------------------------------------------------

app.add_middleware(LoggingMiddleware)
app.add_middleware(SlowAPIMiddleware)

# --------------------------------------------------
# Health Routes
# --------------------------------------------------

app.include_router(
    health.router,
    prefix="/health",
    tags=["Health"],
)

# --------------------------------------------------
# Root Endpoint
# --------------------------------------------------

@app.get(
    "/",
    response_model=RootResponse,
    tags=["Root"],
    summary="Gateway Status",
)
async def root():
    """
    Root endpoint used to verify that
    the API Gateway is running.
    """

>>>>>>> mahendher/round3-api-gateway
    return {
        "message": "API Gateway is running",
        "status": "healthy",
        "version": settings.VERSION,
    }

<<<<<<< HEAD
# Gateway router (keep last because of catch-all route)
=======

# --------------------------------------------------
# Catch-All Gateway Router
# --------------------------------------------------
# NOTE:
# Keep this router LAST because it contains a catch-all
# route (/{path:path}) that forwards requests to the
# appropriate downstream microservice.

>>>>>>> mahendher/round3-api-gateway
app.include_router(gateway.router)