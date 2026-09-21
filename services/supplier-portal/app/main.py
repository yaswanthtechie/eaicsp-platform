from fastapi import FastAPI, Request
import time

from app.routes.supplier_onboarding import (
    router as supplier_onboarding_router,
)
from app.routes.purchase_order import router as purchase_order_router
from app.routes.shipment import router as shipment_router
from app.routes.goods_receipt import router as goods_receipt_router
from app.routes.invoice import router as invoice_router
from app.routes.three_way_match import (
    router as three_way_match_router,
)
from app.routes import supplier_stats_routes
from app.schemas.purchase_order import MessageResponse


app = FastAPI(
    title="Supplier Portal Service",
    version="1.0.0",
    description="Enterprise AI Cognitive Supply Chain",
)


# ============================================================
# REQUEST LOGGING MIDDLEWARE
# ============================================================

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()

    response = await call_next(request)

    process_time = time.time() - start_time

    print(
        f"{request.method} "
        f"{request.url.path} "
        f"- {response.status_code} "
        f"({process_time:.3f}s)",
        flush=True,
    )

    return response


# ============================================================
# SUPPLIER ONBOARDING ROUTES
# ============================================================

app.include_router(
    supplier_onboarding_router,
    prefix="/api/v1",
    tags=["Supplier Onboarding"],
)

# ============================================================
# PURCHASE ORDER ROUTES
# ============================================================

app.include_router(
    purchase_order_router,
    prefix="/api/v1",
    tags=["Purchase Orders"],
)


# ============================================================
# SHIPMENT ROUTES
# ============================================================

app.include_router(
    shipment_router,
    prefix="/api/v1",
    tags=["Shipments"],
)

# ============================================================
# Goods Receipt ROUTES
# ============================================================

app.include_router(
    goods_receipt_router,
    prefix="/api/v1",
    tags=["Goods Receipts"],
)

# ============================================================
# INVOICE ROUTES
# ============================================================

app.include_router(
    invoice_router,
    prefix="/api/v1",
    tags=["Invoices"],
)

# ============================================================
# THREE-WAY MATCH ROUTES
# ============================================================

app.include_router(
    three_way_match_router,
    prefix="/api/v1",
    tags=["Three-Way Matches"],
)

# ============================================================
# SUPPLIER STATS + SCORECARD ROUTES
# ============================================================

app.include_router(
    supplier_stats_routes.router,
    prefix="/api/v1/suppliers",
    tags=["Supplier Stats"],
)


# ============================================================
# ROOT
# ============================================================

@app.get(
    "/",
    response_model=MessageResponse
)
def root():
    return {
        "message": "Supplier Portal Service is running successfully!"
    }