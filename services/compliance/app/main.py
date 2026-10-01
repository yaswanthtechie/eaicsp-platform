import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.core.database import Base, engine
from app.routes.compliance import router as compliance_router
from app.services.sanctions_service import load_all_sanctions
from app.services.sla_service import sla_metrics

from app.models.compliance_override import ComplianceOverride
from app.models.compliance_case import ComplianceCase
from app.models.case_history import CaseHistory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Creating database tables...")

    Base.metadata.create_all(
        bind=engine
    )

    print("Loading sanctions data...")

    load_all_sanctions()

    print("Compliance Service started successfully.")

    logger.info(
        "SLA monitoring started at %s",
        sla_metrics.started_at.isoformat(),
    )

    yield

    print("Compliance Service stopped.")


app = FastAPI(
    title="Compliance Service",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/root")
def health_check():
    return {        
        "service": "compliance",
    }


app.include_router(
    compliance_router,
    prefix="/api/v1/compliance",
)