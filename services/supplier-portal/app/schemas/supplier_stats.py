from pydantic import BaseModel, Field


# ============================================================
# EXISTING SUPPLIER STATS
# ============================================================

class SupplierStatsResponse(BaseModel):
    supplier_id: str

    po_count: int = Field(
        ge=0
    )

    on_time_percentage: float = Field(
        ge=0,
        le=100,
    )

    average_invoice_cycle_time: float = Field(
        ge=0
    )


# ============================================================
# SCORECARD SUMMARY
# ============================================================

class SupplierScorecardMetrics(BaseModel):

    on_time_delivery_percentage: float = Field(
        ge=0,
        le=100,
    )

    dispute_rate_percentage: float = Field(
        ge=0,
        le=100,
    )

    invoice_accuracy_percentage: float = Field(
        ge=0,
        le=100,
    )

    overall_score: float = Field(
        ge=0,
        le=100,
    )


# ============================================================
# PURCHASE ORDER DETAILS
# ============================================================

class SupplierScorecardPurchaseOrders(BaseModel):

    total: int = Field(
        ge=0
    )

    fulfilled: int = Field(
        ge=0
    )

    on_time: int = Field(
        ge=0
    )

    late: int = Field(
        ge=0
    )


# ============================================================
# INVOICE DETAILS
# ============================================================

class SupplierScorecardInvoices(BaseModel):

    total: int = Field(
        ge=0
    )

    disputed: int = Field(
        ge=0
    )

    accurate: int = Field(
        ge=0
    )

    inaccurate: int = Field(
        ge=0
    )


# ============================================================
# SCORECARD DETAILS
# ============================================================

class SupplierScorecardDetails(BaseModel):

    purchase_orders: SupplierScorecardPurchaseOrders

    invoices: SupplierScorecardInvoices


# ============================================================
# FINAL SCORECARD RESPONSE
# ============================================================

class SupplierScorecard(BaseModel):

    supplier_id: str

    scorecard: SupplierScorecardMetrics

    details: SupplierScorecardDetails