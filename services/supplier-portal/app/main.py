from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.supplier_onboarding import (
    router as supplier_onboarding_router,
)
from app.routes.supplier_contract import (
    router as supplier_contract_router,
)
from app.routes.purchase_order import router as purchase_order_router
from app.routes.shipment import router as shipment_router
from app.routes.goods_receipt import router as goods_receipt_router
from app.routes.invoice import router as invoice_router
from app.routes.auth import router as auth_router
from app.schemas.purchase_order import MessageResponse


app = FastAPI(
    title="Supplier Portal Service",
    version="1.0.0",
    description="Enterprise AI Cognitive Supply Chain",
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


app.include_router(
    purchase_order_router,
    prefix="/api/v1",
    tags=["Purchase Orders"],
)

app.include_router(
    invoice_router,
    prefix="/api/v1",
    tags=["Invoices"],
)

app.include_router(
    auth_router,
    prefix="/api/v1",
    tags=["Authentication"],
)


@app.get(
    "/",
    response_model=MessageResponse,
)
def root():
    return {
        "message": "Supplier Portal Service is running successfully!"
    }