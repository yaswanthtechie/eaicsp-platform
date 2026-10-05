import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routes.compliance import router as compliance_router
from app.services.sanctions_service import load_all_sanctions
from app.services.sla_service import sla_metrics
from app.routes.graphql import graphql_router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tables are created by Alembic (`alembic upgrade head`),
    # never by create_all() at startup.
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


app.include_router(
    graphql_router,
    prefix="/api/v1/compliance/graphql",
)