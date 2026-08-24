from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.database import (
    Base,
    engine,
)

from app.routes.compliance import (
    router as compliance_router,
)

from app.services.sanctions_service import (
    load_all_sanctions,
)
from app.models.compliance_override import ComplianceOverride

# =====================================================
# APPLICATION LIFESPAN
# =====================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    print("Creating database tables...")

    Base.metadata.create_all(
        bind=engine
    )

    print("Loading sanctions data...")

    load_all_sanctions()

    print("Compliance Service started successfully.")

    yield

    print("Compliance Service stopped.")


# =====================================================
# FASTAPI APPLICATION
# =====================================================

app = FastAPI(

    title="Compliance Service",

    version="1.0.0",

    lifespan=lifespan,

)


# =====================================================
# ROUTES
# =====================================================

app.include_router(

    compliance_router,

    prefix="/api/v1/compliance",

    tags=["Compliance"],

)