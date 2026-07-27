from fastapi import FastAPI

from app.routes.purchase_order import router as purchase_order_router
from app.routes.invoice import router as invoice_router
from app.schemas.purchase_order import MessageResponse

app = FastAPI(
    title="Supplier Portal Service",
    version="1.0.0",
    description="Enterprise AI Cognitive Supply Chain"
)

app.include_router(
    purchase_order_router,
    prefix="/api/v1",
    tags=["Purchase Orders"]
)

app.include_router(
    invoice_router,
    prefix="/api/v1",
    tags=["Invoices"]
)

@app.get(
    "/",
    response_model=MessageResponse,
)
def root():
    return {
        "message": "Supplier Portal Service is running successfully!"
    }