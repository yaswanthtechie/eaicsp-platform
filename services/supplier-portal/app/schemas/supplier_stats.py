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
# SCORECARD BREAKDOWN
# ============================================================

class SupplierScorecardBreakdownItem(BaseModel):
    """
    Represents one component of the overall supplier score.
    """

    score: float = Field(
        ge=0,
        le=100,
    )

    weight_percentage: float = Field(
        ge=0,
        le=100,
    )

    weighted_score: float = Field(
        ge=0,
        le=100,
    )


class SupplierScorecardBreakdown(BaseModel):
    """
    Breakdown of the overall supplier score.
    """

    on_time_delivery: SupplierScorecardBreakdownItem

    invoice_accuracy: SupplierScorecardBreakdownItem

    dispute_performance: SupplierScorecardBreakdownItem


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

    rating: str = Field(
        min_length=1,
    )

    performance_status: str = Field(
        min_length=1,
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

    pending: int = Field(
        ge=0
    )

    cancelled: int = Field(
        ge=0
    )

    on_time_percentage: float = Field(
        ge=0,
        le=100,
    )

    late_percentage: float = Field(
        ge=0,
        le=100,
    )

    fulfillment_rate: float = Field(
        ge=0,
        le=100,
    )

    average_delay_days: float = Field(
        ge=0
    )

    # NEW:
    # Average time from PO creation to goods receipt.
    average_fulfillment_time_days: float = Field(
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

    approved: int = Field(
        ge=0
    )

    rejected: int = Field(
        ge=0
    )

    pending: int = Field(
        ge=0
    )

    accuracy_percentage: float = Field(
        ge=0,
        le=100,
    )

    dispute_rate_percentage: float = Field(
        ge=0,
        le=100,
    )

    approval_rate_percentage: float = Field(
        ge=0,
        le=100,
    )

    average_cycle_time_days: float = Field(
        ge=0
    )


# ============================================================
# SCORECARD DETAILS
# ============================================================

class SupplierScorecardDetails(BaseModel):

    purchase_orders: SupplierScorecardPurchaseOrders

    invoices: SupplierScorecardInvoices


# ============================================================
# SCORECARD TREND
# ============================================================

class SupplierScorecardTrendItem(BaseModel):
    """
    Represents supplier performance for one time period.

    period:
        Monthly period in YYYY-MM format.

    on_time_percentage:
        Percentage of purchase orders delivered on time.

    dispute_rate_percentage:
        Percentage of invoices that were disputed.

    invoice_accuracy_percentage:
        Percentage of invoices without disputes.

    average_fulfillment_time_days:
        Average time from PO creation to goods receipt.
    """

    period: str = Field(
        min_length=1
    )

    on_time_percentage: float = Field(
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

    average_fulfillment_time_days: float = Field(
        ge=0
    )


# ============================================================
# FINAL SCORECARD RESPONSE
# ============================================================

class SupplierScorecard(BaseModel):

    supplier_id: str

    scorecard: SupplierScorecardMetrics

    score_breakdown: SupplierScorecardBreakdown

    details: SupplierScorecardDetails

    # NEW:
    # Historical performance grouped by month.
    trend: list[SupplierScorecardTrendItem]