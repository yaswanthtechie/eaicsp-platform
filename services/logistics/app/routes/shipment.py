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

    # ========================================================
    # SHIPMENT CRUD
    # ========================================================
    create_shipment,
    get_shipments,
    get_shipment,
    update_shipment,
    delete_shipment,
    shipment_exists,

    # ========================================================
    # QUOTES
    # ========================================================
    get_quotes,
    get_bulk_quotes,

    # ========================================================
    # HISTORY
    # ========================================================
    get_shipment_history,

    # ========================================================
    # R4
    # ========================================================
    get_consolidation_suggestions,
    explain_eta,

    # ========================================================
    # CIRCUIT BREAKER
    # ========================================================
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

@router.post(
    "/",
    status_code=status.HTTP_200_OK,
)
def create_new_shipment(
    data: ShipmentCreate,
):
    """
    Create a new shipment.

    Returns HTTP 200 when the shipment is created successfully.
    """

    if shipment_exists(data.shipment_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Shipment already exists",
        )

    try:
        return create_shipment(data)

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid shipment data.",
        ) from None

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create shipment.",
        ) from None


# ============================================================
# GET ALL SHIPMENTS
# ============================================================

@router.get("/")
def get_all_shipments_route(
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

    try:
        return get_shipments(shipment_status)

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve shipments.",
        ) from None


# ============================================================
# BULK QUOTE - R4
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
            "When true, also runs sequential quoting "
            "and calculates performance."
        ),
    ),
):
    """
    R4 asynchronous bulk quote.

    Maximum 20 shipments.

    Uses asyncio.gather() internally.
    """

    try:
        return await get_bulk_quotes(
            data.shipments,
            benchmark=benchmark,
        )

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bulk quote request.",
        ) from None

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to process bulk quote request.",
        ) from None


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

    try:
        return get_quotes(
            data.origin,
            data.destination,
            data.weight_kg,
            data.preference,
        )

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid quote request.",
        ) from None

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to retrieve shipment quote.",
        ) from None


# ============================================================
# CONSOLIDATION SUGGESTIONS - R4
# ============================================================

@router.get(
    "/consolidation-suggestions",
)
def consolidation_suggestions():
    """
    Return shipment consolidation suggestions.
    """

    try:
        return get_consolidation_suggestions()

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to generate consolidation suggestions.",
        ) from None


# ============================================================
# CIRCUIT BREAKER STATUS - R4
# ============================================================

@router.get(
    "/circuit-breaker-status",
)
def circuit_breaker_status():
    """
    Return circuit breaker status for all carriers.
    """

    try:
        return get_circuit_breaker_status()

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve circuit breaker status.",
        ) from None


# ============================================================
# TRACKING
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

    try:
        shipment = get_shipment(shipment_id)

    except ValueError:
        shipment = None

    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found.",
        )

    adapter = CARRIERS.get(shipment.carrier)

    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported carrier.",
        )

    try:
        return adapter.get_tracking(
            str(shipment_id)
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to retrieve tracking information.",
        ) from None


# ============================================================
# SHIPMENT HISTORY
# ============================================================

@router.get(
    "/{shipment_id}/history",
    response_model=list[ShipmentEvent],
)
def shipment_history(
    shipment_id: int,
):
    """
    Get complete shipment status history.
    """

    try:
        shipment = get_shipment(shipment_id)

    except ValueError:
        shipment = None

    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found.",
        )

    try:
        return get_shipment_history(shipment_id)

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment history not found.",
        ) from None

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve shipment history.",
        ) from None


# ============================================================
# ETA EXPLANATION - R4
# ============================================================

@router.get(
    "/{shipment_id}/eta-explain",
)
def shipment_eta_explain(
    shipment_id: int,
):
    """
    Explain shipment ETA using:

    - route distance
    - carrier
    - estimated days
    - reliability score
    """

    try:
        shipment = get_shipment(shipment_id)

    except ValueError:
        shipment = None

    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found.",
        )

    try:
        return explain_eta(shipment_id)

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unable to generate ETA explanation.",
        ) from None

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to generate ETA explanation.",
        ) from None


# ============================================================
# GET SHIPMENT BY ID
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

    try:
        shipment = get_shipment(shipment_id)

    except ValueError:
        shipment = None

    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found.",
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
    """

    try:
        existing = get_shipment(shipment_id)

    except ValueError:
        existing = None

    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found.",
        )

    # ========================================================
    # PATH ID AND BODY ID
    # ========================================================

    if data.shipment_id != shipment_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shipment ID does not match path ID.",
        )

    # ========================================================
    # UPDATE
    # ========================================================

    try:
        return update_shipment(
            shipment_id,
            data,
        )

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid shipment update.",
        ) from None

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update shipment.",
        ) from None


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

    # ========================================================
    # CHECK EXISTENCE
    # ========================================================

    try:
        existing = get_shipment(shipment_id)

    except ValueError:
        existing = None

    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found.",
        )

    # ========================================================
    # DELETE
    # ========================================================

    try:
        delete_shipment(shipment_id)

        return {
            "message": "Shipment deleted successfully",
        }

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found.",
        ) from None

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to delete shipment.",
        ) from None