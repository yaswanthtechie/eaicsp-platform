from fastapi import APIRouter, HTTPException

from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderHistory,
    PurchaseOrderUpdate,
    PurchaseOrderResponse,
    PurchaseOrderTransition,
    PurchaseOrderStatus,
    MessageResponse
)

from app.services.purchase_order_service import (
    create_purchase_order,
    get_all_purchase_orders,
    get_purchase_order_by_id,
    update_purchase_order,
    delete_purchase_order,
    acknowledge_purchase_order,
    transition_purchase_order,
    get_purchase_order_events,
)

router = APIRouter()

@router.get(
    "/purchase-orders/{po_number}/events",
    response_model=list[PurchaseOrderHistory]
)
def get_po_events(po_number: str):

    events = get_purchase_order_events(po_number)

    if events is None:
        raise HTTPException(
            status_code=404,
            detail="Purchase Order not found"
        )

    return events


# Create Purchase Order
@router.post(
    "/purchase-orders",
    response_model=PurchaseOrderResponse,
    status_code=201
)
def create_po(
    purchase_order: PurchaseOrderCreate,
):
    try:
        return create_purchase_order(
            purchase_order
        )

    except ValueError as e:
        raise HTTPException(
            status_code=409,
            detail=str(e),
        )

# Get All Purchase Orders
@router.get(
    "/purchase-orders",
    response_model=list[PurchaseOrderResponse]
)
def list_purchase_orders():
    return get_all_purchase_orders()


# Get Purchase Order by PO Number
@router.get(
    "/purchase-orders/{po_number}",
    response_model=PurchaseOrderResponse
)
def get_purchase_order(po_number: str):
    po = get_purchase_order_by_id(po_number)

    if not po:
        raise HTTPException(
            status_code=404,
            detail="Purchase Order not found"
        )

    return po


# Update Purchase Order
@router.put(
    "/purchase-orders/{po_number}",
    response_model=PurchaseOrderResponse
)
def update_po(
    po_number: str,
    purchase_order: PurchaseOrderUpdate
):
    updated_po = update_purchase_order(
        po_number,
        purchase_order
    )

    if not updated_po:
        raise HTTPException(
            status_code=404,
            detail="Purchase Order not found"
        )

    return updated_po


# Delete Purchase Order
@router.delete(
    "/purchase-orders/{po_number}",
    response_model=MessageResponse,
)
def delete_po(po_number: str):
    deleted = delete_purchase_order(po_number)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Purchase Order not found"
        )

    return {
        "message": f"Purchase Order '{po_number}' deleted successfully."
    }


# Acknowledge Purchase Order

@router.post(
    "/purchase-orders/{po_number}/acknowledge",
    response_model=PurchaseOrderResponse
)
def acknowledge_po(po_number: str):
    try:
        purchase_order = acknowledge_purchase_order(po_number)

        if not purchase_order:
            raise HTTPException(
                status_code=404,
                detail="Purchase Order not found"
            )

        return purchase_order

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    

    # transition state machine for purchase order

@router.post(
    "/purchase-orders/{po_number}/transition",
    response_model=PurchaseOrderResponse
)
def transition_po(
    po_number: str,
    transition: PurchaseOrderTransition
):
    try:

        purchase_order = transition_purchase_order(
            po_number,
            transition.actor,
            transition.target_state
        )

        if not purchase_order:
            raise HTTPException(
                status_code=404,
                detail="Purchase Order not found"
            )

        return purchase_order

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )