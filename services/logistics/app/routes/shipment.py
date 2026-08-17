from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.shipment import (
    ShipmentCreate,
    Status,
    QuoteRequest,
    QuoteResponse,
    BulkQuoteRequest,
    BulkQuoteResponse,
    ShipmentEvent,
    TrackingInfo,
)

from app.services.shipment_service import (
    CARRIERS,

    # --------------------------------------------------------
    # SHIPMENT CRUD
    # --------------------------------------------------------
    create_shipment,
    get_all_shipments,
    get_shipment,
    update_shipment,
    delete_shipment,
    filter_shipments_by_status,
    shipment_exists,

    # --------------------------------------------------------
    # QUOTES
    # --------------------------------------------------------
    get_quotes,
    get_bulk_quotes,

    # --------------------------------------------------------
    # HISTORY
    # --------------------------------------------------------
    get_shipment_history,

    # --------------------------------------------------------
    # R4
    # --------------------------------------------------------
    get_consolidation_suggestions,
    explain_eta,

    # --------------------------------------------------------
    # CIRCUIT BREAKER
    # --------------------------------------------------------
    get_circuit_breaker_status,
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/v1/shipments",
    tags=["Shipments"],
)


# ============================================================
# CREATE SHIPMENT
# ============================================================

@router.post("/")
def create_new_shipment(
    data: ShipmentCreate,
):
    """
    Create a new shipment.
    """

    if shipment_exists(data.shipment_id):

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Shipment already exists",
        )

    return create_shipment(data)


# ============================================================
# GET ALL SHIPMENTS
# ============================================================

@router.get("/")
def get_shipments(
    shipment_status: Optional[Status] = Query(
        default=None,
        alias="status",
        description="Filter shipments by status.",
    ),
):
    """
    Get all shipments.

    Optional filter:

        ?status=pending
        ?status=in_transit
        ?status=delivered
        ?status=delayed
        ?status=cancelled
    """

    if shipment_status is not None:

        return filter_shipments_by_status(
            shipment_status
        )

    return get_all_shipments()


# ============================================================
# BULK QUOTE - R4
#
# IMPORTANT:
# This route must be before /{shipment_id}
# ============================================================

@router.post(
    "/bulk-quote",
    response_model=BulkQuoteResponse,
)
async def shipment_bulk_quote(
    data: BulkQuoteRequest,
    benchmark: bool = Query(
        default=False,
        description=(
            "Run sequential quoting also and "
            "calculate parallel speedup."
        ),
    ),
):
    """
    R4 asynchronous bulk quotation.

    Normal:

        POST /api/v1/shipments/bulk-quote

    Benchmark:

        POST /api/v1/shipments/bulk-quote?benchmark=true

    The service uses asyncio.gather() to process
    multiple shipment quotes in parallel.

    Maximum batch size:

        20 shipments
    """

    try:

        result = await get_bulk_quotes(
            data.shipments,
            benchmark=benchmark,
        )

        return result

    except ValueError as exc:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


# ============================================================
# SINGLE QUOTE
# ============================================================

@router.post(
    "/quote",
    response_model=QuoteResponse,
)
def shipment_quote(
    data: QuoteRequest,
):
    """
    Get a quote for one shipment.
    """

    return get_quotes(
        data.origin,
        data.destination,
        data.weight_kg,
        data.preference,
    )


# ============================================================
# CONSOLIDATION SUGGESTIONS - R4
#
# IMPORTANT:
# This route must be before /{shipment_id}
# ============================================================

@router.get(
    "/consolidation-suggestions",
)
def consolidation_suggestions():
    """
    R4 rule-based shipment consolidation.

    Suggest combining shipments when:

    1. There are at least 2 shipments.
    2. They have the same destination.
    3. Their estimated delivery dates are within 2 days.
    """

    return get_consolidation_suggestions()


# ============================================================
# CIRCUIT BREAKER STATUS - R4
#
# IMPORTANT:
# This route must be before /{shipment_id}
# ============================================================

@router.get(
    "/circuit-breaker-status",
)
def circuit_breaker_status():
    """
    Return local circuit breaker status
    for every carrier.
    """

    return get_circuit_breaker_status()


# ============================================================
# TRACK SHIPMENT
#
# IMPORTANT:
# This route must be before /{shipment_id}
# ============================================================

@router.get(
    "/{shipment_id}/tracking",
    response_model=TrackingInfo,
)
def track_shipment(
    shipment_id: int,
):
    """
    Get tracking information for a shipment.
    """

    shipment = get_shipment(
        shipment_id
    )

    if shipment is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found",
        )

    carrier = shipment.carrier

    adapter = CARRIERS.get(
        carrier
    )

    if adapter is None:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported carrier",
        )

    try:

        return adapter.get_tracking(
            str(shipment_id)
        )

    except Exception as exc:

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )


# ============================================================
# SHIPMENT HISTORY
#
# IMPORTANT:
# This route must be before /{shipment_id}
# ============================================================

@router.get(
    "/{shipment_id}/history",
    response_model=list[ShipmentEvent],
)
def shipment_history(
    shipment_id: int,
):
    """
    Get complete status history
    of a shipment.
    """

    shipment = get_shipment(
        shipment_id
    )

    if shipment is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found",
        )

    return get_shipment_history(
        shipment_id
    )


# ============================================================
# ETA EXPLANATION - R4 STRETCH
#
# IMPORTANT:
# This route must be before /{shipment_id}
# ============================================================

@router.get(
    "/{shipment_id}/eta-explain",
)
def shipment_eta_explain(
    shipment_id: int,
):
    """
    R4 stretch feature.

    Explain the ETA using:

    - Origin
    - Destination
    - Route distance
    - Carrier baseline
    - Dynamic reliability score
    - Estimated days
    - Weather flag
    """

    shipment = get_shipment(
        shipment_id
    )

    if shipment is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found",
        )

    try:

        return explain_eta(
            shipment_id
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


# ============================================================
# GET SHIPMENT BY ID
#
# IMPORTANT:
# Keep this AFTER all specific routes.
# ============================================================

@router.get(
    "/{shipment_id}",
)
def get_one_shipment(
    shipment_id: int,
):
    """
    Get one shipment by ID.
    """

    shipment = get_shipment(
        shipment_id
    )

    if shipment is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found",
        )

    return shipment


# ============================================================
# UPDATE SHIPMENT
# ============================================================

@router.put(
    "/{shipment_id}",
)
def update_existing_shipment(
    shipment_id: int,
    data: ShipmentCreate,
):
    """
    Update an existing shipment.

    Status transition validation is handled
    inside shipment_service.py.
    """

    shipment = get_shipment(
        shipment_id
    )

    if shipment is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found",
        )

    # --------------------------------------------------------
    # CHECK PATH ID AND BODY ID
    # --------------------------------------------------------

    if data.shipment_id != shipment_id:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Shipment ID in body does not "
                "match path ID"
            ),
        )

    # --------------------------------------------------------
    # UPDATE
    # --------------------------------------------------------

    try:

        return update_shipment(
            shipment_id,
            data,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


# ============================================================
# DELETE SHIPMENT
# ============================================================

@router.delete(
    "/{shipment_id}",
)
def delete_existing_shipment(
    shipment_id: int,
):
    """
    Delete a shipment by ID.
    """

    shipment = delete_shipment(
        shipment_id
    )

    if shipment is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found",
        )

    return {
        "message": "Shipment deleted successfully"
    }