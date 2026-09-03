from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import (
    require_roles,
    verify_token,
)

from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderHistory,
    PurchaseOrderUpdate,
    PurchaseOrderResponse,
    PurchaseOrderTransition,
    MessageResponse,
    BulkPOSendRequest,
    BulkPOSendResponse,
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
    bulk_send_purchase_orders,
)


router = APIRouter()


# ============================================================
# SUPPLIER PURCHASE ORDER ACCESS
# ============================================================

def require_supplier_po_access(
    po_number: str,
    user=Depends(verify_token),
):
    """
    Authenticate the supplier and verify that the supplier
    owns the requested Purchase Order.

    Rules:
        1. User must have the supplier role.
        2. Authenticated user must have a supplier_id.
        3. Authenticated supplier_id must match the PO supplier_id.

    This prevents Supplier A from accessing Supplier B's PO.
    """

    # --------------------------------------------------------
    # 1. Role check
    # --------------------------------------------------------

    if user.get("role") != "supplier":
        raise HTTPException(
            status_code=403,
            detail="Forbidden: supplier access required",
        )

    # --------------------------------------------------------
    # 2. Get supplier identity
    # --------------------------------------------------------

    authenticated_supplier_id = user.get("supplier_id")

    if not authenticated_supplier_id:
        raise HTTPException(
            status_code=403,
            detail="Supplier identity is missing",
        )

    # --------------------------------------------------------
    # 3. Find Purchase Order
    # --------------------------------------------------------

    purchase_order = get_purchase_order_by_id(po_number)

    if not purchase_order:
        raise HTTPException(
            status_code=404,
            detail="Purchase Order not found",
        )

    # --------------------------------------------------------
    # 4. Supplier scoping check
    # --------------------------------------------------------

    if (
        authenticated_supplier_id
        != purchase_order["supplier_id"]
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Forbidden: supplier does not own "
                "this Purchase Order"
            ),
        )

    return user, purchase_order


def require_supplier_po_event_access(
    po_number: str,
    user=Depends(verify_token),
):
    """
    Authorize access to Purchase Order audit history.

    Event history remains available even after the Purchase
    Order itself has been deleted.

    Rules:
        1. User must have the supplier role.
        2. User must have a supplier_id.
        3. If PO exists, verify ownership using the PO.
        4. If PO was deleted, verify ownership using the
           supplier_id stored in the historical events.
    """

    # --------------------------------------------------------
    # 1. Role check
    # --------------------------------------------------------

    if user.get("role") != "supplier":
        raise HTTPException(
            status_code=403,
            detail="Forbidden: supplier access required",
        )

    # --------------------------------------------------------
    # 2. Get authenticated supplier identity
    # --------------------------------------------------------

    authenticated_supplier_id = user.get("supplier_id")

    if not authenticated_supplier_id:
        raise HTTPException(
            status_code=403,
            detail="Supplier identity is missing",
        )

    # --------------------------------------------------------
    # 3. Get preserved event history
    # --------------------------------------------------------

    events = get_purchase_order_events(po_number)

    if events is None:
        raise HTTPException(
            status_code=404,
            detail="Purchase Order not found",
        )

    # --------------------------------------------------------
    # 4. If PO still exists, use current PO ownership
    # --------------------------------------------------------

    purchase_order = get_purchase_order_by_id(po_number)

    if purchase_order:

        if (
            authenticated_supplier_id
            != purchase_order["supplier_id"]
        ):
            raise HTTPException(
                status_code=403,
                detail=(
                    "Forbidden: supplier does not own "
                    "this Purchase Order"
                ),
            )

        return user, events

    # --------------------------------------------------------
    # 5. PO was deleted
    #
    # Use preserved audit events to verify ownership.
    # --------------------------------------------------------

    if not events:
        raise HTTPException(
            status_code=404,
            detail="Purchase Order not found",
        )

    event_supplier_ids = {
        event.get("supplier_id")
        for event in events
    }

    if authenticated_supplier_id not in event_supplier_ids:
        raise HTTPException(
            status_code=403,
            detail=(
                "Forbidden: supplier does not own "
                "this Purchase Order history"
            ),
        )

    return user, events


# ============================================================
# GET PURCHASE ORDER EVENTS
# Supplier-facing endpoint
# Requires: supplier role + supplier_id scoping
# ============================================================

@router.get(
    "/purchase-orders/{po_number}/events",
    response_model=list[PurchaseOrderHistory],
)
def get_po_events(
    access=Depends(require_supplier_po_event_access),
):
    """
    Get Purchase Order audit events.

    Historical events remain accessible to the owning
    supplier even after the Purchase Order is deleted.
    """

    user, events = access

    return events



# ============================================================
# CREATE PURCHASE ORDER
# ============================================================

@router.post(
    "/purchase-orders",
    response_model=PurchaseOrderResponse,
    status_code=201,
)
def create_po(
    purchase_order: PurchaseOrderCreate,
):
    try:
        return create_purchase_order(purchase_order)

    except ValueError as e:
        message = str(e)

        # Duplicate PO → 409 Conflict
        if "already exists" in message:
            raise HTTPException(
                status_code=409,
                detail=message,
            )

        # Invalid business data → 400 Bad Request
        raise HTTPException(
            status_code=400,
            detail=message,
        )


# ============================================================
# BULK SEND PURCHASE ORDERS
# Requires: procurement_manager
# ============================================================

@router.post(
    "/purchase-orders/bulk-send",
    response_model=BulkPOSendResponse,
)
def bulk_send_po(
    request: BulkPOSendRequest,
    user=Depends(
        require_roles("procurement_manager")
    ),
):
    try:
        # verify_token() returns the user dictionary
        # from Rahul's Platform Service.
        actor = user.get("email")

        if not actor:
            raise HTTPException(
                status_code=500,
                detail="Authenticated user identity is missing",
            )

        return bulk_send_purchase_orders(
            request.po_numbers,
            actor,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


# ============================================================
# GET ALL PURCHASE ORDERS
# ============================================================

@router.get(
    "/purchase-orders",
    response_model=list[PurchaseOrderResponse],
)
def list_purchase_orders():

    return get_all_purchase_orders()


# ============================================================
# GET PURCHASE ORDER BY PO NUMBER
# Supplier-facing endpoint
# Requires: supplier role + supplier_id scoping
# ============================================================

@router.get(
    "/purchase-orders/{po_number}",
    response_model=PurchaseOrderResponse,
)
def get_purchase_order(
    access=Depends(require_supplier_po_access),
):

    user, purchase_order = access

    return purchase_order


# ============================================================
# UPDATE PURCHASE ORDER
# ============================================================

@router.put(
    "/purchase-orders/{po_number}",
    response_model=PurchaseOrderResponse,
)
def update_po(
    po_number: str,
    purchase_order: PurchaseOrderUpdate,
):
    try:
        updated_po = update_purchase_order(
            po_number,
            purchase_order,
        )

        if not updated_po:
            raise HTTPException(
                status_code=404,
                detail="Purchase Order not found",
            )

        return updated_po

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


# ============================================================
# DELETE PURCHASE ORDER
# ============================================================

@router.delete(
    "/purchase-orders/{po_number}",
    response_model=MessageResponse,
)
def delete_po(po_number: str):

    deleted = delete_purchase_order(po_number)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Purchase Order not found",
        )

    return {
        "message": (
            f"Purchase Order '{po_number}' "
            "deleted successfully."
        )
    }


# ============================================================
# ACKNOWLEDGE PURCHASE ORDER
# Supplier-facing endpoint
# Requires: supplier role + supplier_id scoping
# ============================================================

@router.post(
    "/purchase-orders/{po_number}/acknowledge",
    response_model=PurchaseOrderResponse,
)
def acknowledge_po(
    access=Depends(require_supplier_po_access),
):

    user, purchase_order = access

    po_number = purchase_order["po_number"]

    try:

        purchase_order = acknowledge_purchase_order(
            po_number
        )

        if not purchase_order:
            raise HTTPException(
                status_code=404,
                detail="Purchase Order not found",
            )

        return purchase_order

    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


# ============================================================
# TRANSITION PURCHASE ORDER
# ============================================================

@router.post(
    "/purchase-orders/{po_number}/transition",
    response_model=PurchaseOrderResponse,
)
def transition_po(
    po_number: str,
    transition: PurchaseOrderTransition,
):

    try:

        purchase_order = transition_purchase_order(
            po_number,
            transition.actor,
            transition.target_state,
        )

        if not purchase_order:
            raise HTTPException(
                status_code=404,
                detail="Purchase Order not found",
            )

        return purchase_order

    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

