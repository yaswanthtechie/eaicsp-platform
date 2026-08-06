from fastapi import APIRouter, HTTPException
from typing import Optional

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
    create_shipment,
    get_all_shipments,
    get_shipment,
    update_shipment,
    delete_shipment,
    filter_shipments_by_status,
    shipment_exists,
    get_quotes,
    get_bulk_quotes,
    get_shipment_history,
)


router = APIRouter(
    prefix="/api/v1/shipments",
    tags=["Shipments"]
)


# CREATE SHIPMENT
@router.post("/")
def create_new_shipment(data: ShipmentCreate):

    if shipment_exists(data.shipment_id):

        raise HTTPException(
            status_code=409,
            detail="Shipment already exists"
        )

    return create_shipment(data)


# GET ALL SHIPMENTS
@router.get("/")
def get_shipments(
    status: Optional[Status] = None
):

    if status:

        return filter_shipments_by_status(status)

    return get_all_shipments()



# GET SHIPMENT BY ID
@router.get("/{shipment_id}")
def get_one_shipment(
    shipment_id: int
):

    shipment = get_shipment(shipment_id)

    if shipment is None:

        raise HTTPException(
            status_code=404,
            detail="Shipment not found"
        )

    return shipment


# UPDATE SHIPMENT
@router.put("/{shipment_id}")
def update_existing_shipment(
    shipment_id: int,
    data: ShipmentCreate
):

    shipment = get_shipment(shipment_id)

    if shipment is None:

        raise HTTPException(
            status_code=404,
            detail="Shipment not found"
        )

    if data.shipment_id != shipment_id:

        raise HTTPException(
            status_code=400,
            detail="Shipment ID in body does not match path ID"
        )

    try:
        return update_shipment(
            shipment_id,
            data
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )


# DELETE SHIPMENT
@router.delete("/{shipment_id}")
def delete_existing_shipment(
    shipment_id: int
):

    shipment = delete_shipment(shipment_id)

    if shipment is None:

        raise HTTPException(
            status_code=404,
            detail="Shipment not found"
        )

    return {
        "message": "Shipment deleted successfully"
    }


# TRACK SHIPMENT
@router.get(
    "/{shipment_id}/tracking",
    response_model=TrackingInfo
)
def track_shipment(
    shipment_id: int
):

    shipment = get_shipment(shipment_id)

    if shipment is None:

        raise HTTPException(
            status_code=404,
            detail="Shipment not found"
        )

    adapter = CARRIERS.get(
        shipment.carrier
    )

    if adapter is None:

        raise HTTPException(
            status_code=400,
            detail="Unsupported carrier"
        )

    return adapter.get_tracking(
        str(shipment_id)
    )
# GET QUOTE
@router.post(
    "/quote",
    response_model=QuoteResponse,
)
def shipment_quote(
    data: QuoteRequest
):

    return get_quotes(
        data.origin,
        data.destination,
        data.weight_kg,
        data.preference,
    )


# BULK QUOTE
@router.post(
    "/bulk-quote",
    response_model=BulkQuoteResponse,
)
async def shipment_bulk_quote(
    data: BulkQuoteRequest
):
    quotes = await get_bulk_quotes(data.shipments)
    return BulkQuoteResponse(quotes=quotes)



# SHIPMENT HISTORY
@router.get(
    "/{shipment_id}/history",
    response_model=list[ShipmentEvent]
)
def shipment_history(
    shipment_id: int
):
    shipment = get_shipment(shipment_id)

    if shipment is None:

        raise HTTPException(
            status_code=404,
            detail="Shipment not found"
        )

    return get_shipment_history(shipment_id)