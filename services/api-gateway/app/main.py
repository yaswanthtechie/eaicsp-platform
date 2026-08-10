"""
Main FastAPI application for the API Gateway.
"""

import httpx
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.middleware.logging import LoggingMiddleware
from app.middleware.request_id import RequestIDMiddleware
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

app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
)

# --------------------------------------------------
# Middlewares
# --------------------------------------------------

app.add_middleware(LoggingMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestIDMiddleware)

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

    return {
        "message": "API Gateway is running",
        "status": "healthy",
        "version": settings.VERSION,
    }


# --------------------------------------------------
# Catch-All Gateway Router
# --------------------------------------------------
# NOTE:
# Keep this router LAST because it contains a catch-all
# route (/{path:path}) that forwards requests to the
# appropriate downstream microservice.

app.include_router(gateway.router)