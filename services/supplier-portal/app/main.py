from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager

from app.services.kafka_consumer_runner import kafka_consumer_runner
from app.services.inv_po_approved_consumer_runner import (
    inv_po_approved_consumer_runner,
)
from app.services.po_ack_outbox_publisher import (
    po_ack_outbox_publisher_runner,
)
from app.routes.supplier_onboarding import (
    router as supplier_onboarding_router,
)
from app.routes.supplier_contract import (
    router as supplier_contract_router,
)
from app.routes.purchase_order import router as purchase_order_router
from app.routes.approved_purchase_orders import (
    router as approved_purchase_orders_router,
)
from app.routes.shipment import router as shipment_router
from app.routes.goods_receipt import router as goods_receipt_router
from app.routes.invoice import router as invoice_router
from app.routes.supplier_stats_routes import (
    router as supplier_stats_router,
)
from app.routes.three_way_match import (
    router as three_way_match_router,
)
from app.routes.auth import router as auth_router
from app.schemas.purchase_order import MessageResponse
from strawberry.fastapi import GraphQLRouter

from app.graphql.context import get_graphql_context
from app.graphql.schema import schema
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Start and stop Supplier Portal Kafka consumers
    with the FastAPI application lifecycle.
    """
    if settings.KAFKA_ENABLED:
        kafka_consumer_runner.start()
        inventory_goods_received_runner.start()

    if settings.PO_KAFKA_ENABLED:
        inv_po_approved_consumer_runner.start()

    if settings.PO_OUTBOX_ENABLED:
        po_ack_outbox_publisher_runner.start()

    try:
        yield
    finally:
        if settings.PO_OUTBOX_ENABLED:
            po_ack_outbox_publisher_runner.stop()

        if settings.PO_KAFKA_ENABLED:
            inv_po_approved_consumer_runner.stop()

        if settings.KAFKA_ENABLED:
            inventory_goods_received_runner.stop()
            kafka_consumer_runner.stop()

app = FastAPI(
    title="Supplier Portal Service",
    version="1.0.0",
    description="Enterprise AI Cognitive Supply Chain",
    lifespan=lifespan,
)

graphql_app = GraphQLRouter(
    schema,
    context_getter=get_graphql_context,
)

# Allow the React/Vite frontend to communicate with the backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(approved_purchase_orders_router)

# Supplier Onboarding
app.include_router(
    supplier_onboarding_router,
    prefix="/api/v1",
    tags=["Supplier Onboarding"],
)

# Supplier Contracts
app.include_router(
    supplier_contract_router,
    prefix="/api/v1",
    tags=["Supplier Contracts"],
)


# Purchase Orders
app.include_router(
    purchase_order_router,
    prefix="/api/v1",
    tags=["Purchase Orders"],
)


# Shipments
app.include_router(
    shipment_router,
    prefix="/api/v1",
    tags=["Shipments"],
)

# Invoices
app.include_router(
    invoice_router,
    prefix="/api/v1",
    tags=["Invoices"],
)

# Authentication
app.include_router(
    auth_router,
    prefix="/api/v1",
    tags=["Authentication"],
)

# Goods Receipts
app.include_router(
    goods_receipt_router,
    prefix="/api/v1",
    tags=["Goods Receipts"],
)


# Three-Way Match
app.include_router(
    three_way_match_router,
    prefix="/api/v1",
    tags=["Three-Way Match"],
)

# Supplier Stats & Scorecard
app.include_router(
    supplier_stats_router,
    prefix="/api/v1/suppliers",
    tags=["Supplier Stats"],
)

app.include_router(
    graphql_app,
    prefix="/graphql",
)

@app.get(
    "/",
    response_model=MessageResponse,
)
def root():
    return {
        "message": "Supplier Portal Service is running successfully!"
    }



@app.get("/health")
def health():
    return {
        "status": "healthy",
        "kafka_consumer_alive": (
            kafka_consumer_runner.is_alive()
            if settings.KAFKA_ENABLED
            else False
        ),
        "po_kafka_consumer_alive": (
            inv_po_approved_consumer_runner.is_alive()
            if settings.PO_KAFKA_ENABLED
            else False
        ),
            "po_outbox_publisher_alive": (
            po_ack_outbox_publisher_runner.is_alive()
            if settings.PO_OUTBOX_ENABLED
            else False
        ),
    }
