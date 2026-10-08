from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import (
    require_roles,
    require_supplier_view_access,
    require_supplier_write_access,
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


def require_po_access(supplier_only: bool = False):
    """
    Purchase Order access guard.

    supplier_only=False:
        Suppliers can VIEW only their own POs.
        Internal roles can access any PO.

    supplier_only=True:
        Only the owning supplier can perform the action.
        Supplier must have CLEARED compliance access.
        Internal roles are not allowed.
    """

    def dependency(
        po_number: str,
        user=Depends(
            require_supplier_write_access
            if supplier_only
            else require_supplier_view_access
        ),
    ):
        # ----------------------------------------------------
        # 1. Supplier identity validation
        # ----------------------------------------------------

        if user.get("role") == "supplier":
            authenticated_supplier_id = user.get("supplier_id")

            if not authenticated_supplier_id:
                raise HTTPException(
                    status_code=403,
                    detail="Supplier identity is missing",
                )

        # ----------------------------------------------------
        # 2. Supplier-only action
        # ----------------------------------------------------

        elif supplier_only:
            raise HTTPException(
                status_code=403,
                detail="Forbidden: supplier access required",
            )

        # ----------------------------------------------------
        # 3. Find Purchase Order
        # ----------------------------------------------------

        purchase_order = get_purchase_order_by_id(po_number)

        if not purchase_order:
            raise HTTPException(
                status_code=404,
                detail="Purchase Order not found",
            )

        # ----------------------------------------------------
        # 4. Supplier ownership / scoping
        # ----------------------------------------------------

        if (
            user.get("role") == "supplier"
            and user["supplier_id"]
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

    return dependency


# ============================================================
# PURCHASE ORDER EVENT HISTORY ACCESS
# ============================================================


def require_po_event_access(
    po_number: str,
    user=Depends(require_supplier_view_access),
):
    """
    Authorize access to Purchase Order audit history.

    Internal users:
        Can view any PO event history.

    Suppliers:
        Can view only their own PO event history.

    Suspended suppliers:
        Cannot access PO history.

    Needs-review suppliers:
        Can view PO history.

    Event history remains available even after the PO
    itself has been deleted.
    """

    # --------------------------------------------------------
    # 1. Get authenticated supplier identity
    # --------------------------------------------------------

    authenticated_supplier_id = user.get("supplier_id")

    if (
        user.get("role") == "supplier"
        and not authenticated_supplier_id
    ):
        raise HTTPException(
            status_code=403,
            detail="Supplier identity is missing",
        )

    # --------------------------------------------------------
    # 2. Get preserved event history
    # --------------------------------------------------------

    events = get_purchase_order_events(po_number)

    if events is None:
        raise HTTPException(
            status_code=404,
            detail="Purchase Order not found",
        )

    # --------------------------------------------------------
    # 3. If PO still exists, use current PO ownership
    # --------------------------------------------------------

    purchase_order = get_purchase_order_by_id(po_number)

    if purchase_order:

        if (
            user.get("role") == "supplier"
            and authenticated_supplier_id
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
    # 4. PO was deleted.
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

    if (
        user.get("role") == "supplier"
        and authenticated_supplier_id
        not in event_supplier_ids
    ):
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
#
# Supplier:
#   CLEARED      -> allowed
#   NEEDS_REVIEW -> allowed
#   SUSPENDED    -> 403
#
# Internal users:
#   Existing access preserved
# ============================================================


@router.get(
    "/purchase-orders/{po_number}/events",
    response_model=list[PurchaseOrderHistory],
)
def get_po_events(
    po_number: str,
    access=Depends(require_po_event_access),
):
    """
    Get Purchase Order audit events.

    Historical events remain accessible to the owning
    supplier even after the Purchase Order is deleted.

    Compliance enforcement is performed before this
    endpoint executes.
    """

    user, events = access

    return events


# ============================================================
# CREATE PURCHASE ORDER
# Requires: procurement_manager
# ============================================================


@router.post(
    "/purchase-orders",
    response_model=PurchaseOrderResponse,
    status_code=201,
)
def create_po(
    purchase_order: PurchaseOrderCreate,
    user=Depends(
        require_roles("procurement_manager")
    ),
):
    """
    Create a new Purchase Order.

    Authorization:
        - procurement_manager -> allowed
        - supplier -> forbidden
        - all other roles -> forbidden
    """

    try:
        return create_purchase_order(
            purchase_order
        )

    except ValueError as e:
        message = str(e)

        # ----------------------------------------------------
        # Duplicate PO -> 409 Conflict
        # ----------------------------------------------------

        if "already exists" in message:
            raise HTTPException(
                status_code=409,
                detail=message,
            )

        # ----------------------------------------------------
        # Invalid business data -> 400 Bad Request
        # ----------------------------------------------------

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
    """
    Bulk-send Purchase Orders.

    This is an internal procurement operation and is not
    restricted by supplier compliance access state.
    """

    try:
        # verify_token() is used internally by require_roles().
        # The authenticated user's email is the actor.
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
#
# Supplier:
#   CLEARED      -> allowed
#   NEEDS_REVIEW -> allowed
#   SUSPENDED    -> 403
#
# Internal users:
#   Can view all POs.
# ============================================================


@router.get(
    "/purchase-orders",
    response_model=list[PurchaseOrderResponse],
)
def list_purchase_orders(
    user=Depends(require_supplier_view_access),
):
    """
    Get Purchase Orders.

    Supplier:
        Returns only Purchase Orders belonging to the
        authenticated supplier.

    Internal users:
        Returns all Purchase Orders.

    Compliance access:
        CLEARED      -> allowed
        NEEDS_REVIEW -> allowed
        SUSPENDED    -> rejected
    """

    # --------------------------------------------------------
    # Supplier users are strictly scoped to their own POs
    # --------------------------------------------------------

    if user.get("role") == "supplier":

        authenticated_supplier_id = user.get("supplier_id")

        if not authenticated_supplier_id:
            raise HTTPException(
                status_code=403,
                detail="Supplier identity is missing",
            )

        purchase_orders = get_all_purchase_orders()

        return [
            purchase_order
            for purchase_order in purchase_orders
            if purchase_order.get("supplier_id")
            == authenticated_supplier_id
        ]

    # --------------------------------------------------------
    # Internal users can view all Purchase Orders
    # --------------------------------------------------------

    return get_all_purchase_orders()


# ============================================================
# GET PURCHASE ORDER BY PO NUMBER
#
# Supplier:
#   CLEARED      -> allowed
#   NEEDS_REVIEW -> allowed
#   SUSPENDED    -> 403
#
# Supplier scoping remains enforced.
# ============================================================


@router.get(
    "/purchase-orders/{po_number}",
    response_model=PurchaseOrderResponse,
)
def get_purchase_order(
    access=Depends(require_po_access()),
):
    """
    Get a Purchase Order.

    Supplier compliance access is checked before the PO
    lookup and supplier ownership check.
    """

    user, purchase_order = access

    return purchase_order


# ============================================================
# UPDATE PURCHASE ORDER
#
# Supplier:
#   CLEARED      -> allowed for own PO
#   NEEDS_REVIEW -> 403
#   SUSPENDED    -> 403
#
# Procurement Manager:
#   Can update any PO.
#
# Other roles:
#   Forbidden.
# ============================================================


@router.put(
    "/purchase-orders/{po_number}",
    response_model=PurchaseOrderResponse,
)
def update_po(
    po_number: str,
    purchase_order: PurchaseOrderUpdate,
    user=Depends(require_supplier_write_access),
):
    """
    Update a Purchase Order.

    Supplier compliance rules:

        CLEARED:
            Supplier may update its own PO.

        NEEDS_REVIEW:
            Supplier may not perform write operations.

        SUSPENDED:
            Supplier access is completely blocked.

    Procurement managers remain unaffected by supplier
    compliance access restrictions.
    """

    # --------------------------------------------------------
    # Get requested Purchase Order
    # --------------------------------------------------------

    existing_po = get_purchase_order_by_id(po_number)

    if not existing_po:
        raise HTTPException(
            status_code=404,
            detail="Purchase Order not found",
        )

    user_role = user.get("role")

    # --------------------------------------------------------
    # Supplier authorization + supplier scoping
    # --------------------------------------------------------

    if user_role == "supplier":

        authenticated_supplier_id = user.get("supplier_id")

        if not authenticated_supplier_id:
            raise HTTPException(
                status_code=403,
                detail="Supplier identity is missing",
            )

        if (
            authenticated_supplier_id
            != existing_po.get("supplier_id")
        ):
            raise HTTPException(
                status_code=403,
                detail=(
                    "Forbidden: supplier does not own "
                    "this Purchase Order"
                ),
            )

    # --------------------------------------------------------
    # Procurement manager can update any PO
    # --------------------------------------------------------

    elif user_role == "procurement_manager":
        pass

    # --------------------------------------------------------
    # All other roles are forbidden
    # --------------------------------------------------------

    else:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: insufficient permissions",
        )

    # --------------------------------------------------------
    # Perform update
    # --------------------------------------------------------

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
#
# Supplier:
#   CLEARED      -> allowed for own PO
#   NEEDS_REVIEW -> 403
#   SUSPENDED    -> 403
#
# Procurement Manager:
#   Can delete any PO.
#
# Other roles:
#   Forbidden.
# ============================================================


@router.delete(
    "/purchase-orders/{po_number}",
    response_model=MessageResponse,
)
def delete_po(
    po_number: str,
    user=Depends(require_supplier_write_access),
):
    """
    Delete a Purchase Order.

    Supplier compliance rules:

        CLEARED:
            Supplier may delete its own PO.

        NEEDS_REVIEW:
            Supplier may not perform write operations.

        SUSPENDED:
            Supplier access is completely blocked.

    Procurement managers remain unaffected.
    """

    # --------------------------------------------------------
    # Get requested Purchase Order
    # --------------------------------------------------------

    existing_po = get_purchase_order_by_id(po_number)

    if not existing_po:
        raise HTTPException(
            status_code=404,
            detail="Purchase Order not found",
        )

    user_role = user.get("role")

    # --------------------------------------------------------
    # Supplier authorization + supplier scoping
    # --------------------------------------------------------

    if user_role == "supplier":

        authenticated_supplier_id = user.get("supplier_id")

        if not authenticated_supplier_id:
            raise HTTPException(
                status_code=403,
                detail="Supplier identity is missing",
            )

        if (
            authenticated_supplier_id
            != existing_po.get("supplier_id")
        ):
            raise HTTPException(
                status_code=403,
                detail=(
                    "Forbidden: supplier does not own "
                    "this Purchase Order"
                ),
            )

    # --------------------------------------------------------
    # Procurement manager can delete any PO
    # --------------------------------------------------------

    elif user_role == "procurement_manager":
        pass

    # --------------------------------------------------------
    # All other roles are forbidden
    # --------------------------------------------------------

    else:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: insufficient permissions",
        )

    # --------------------------------------------------------
    # Perform deletion
    # --------------------------------------------------------

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
#
# Supplier:
#   CLEARED      -> allowed for own PO
#   NEEDS_REVIEW -> 403
#   SUSPENDED    -> 403
#
# Only the owning supplier can acknowledge.
# ============================================================


@router.post(
    "/purchase-orders/{po_number}/acknowledge",
    response_model=PurchaseOrderResponse,
)
def acknowledge_po(
    access=Depends(
        require_po_access(supplier_only=True)
    ),
):
    """
    Acknowledge a Purchase Order.

    This endpoint uses supplier-only PO access, which now
    includes the Round 14 supplier write-compliance check.
    """

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
# Requires: procurement_manager
#
# Internal procurement operation.
# Supplier compliance status does not affect this endpoint.
# ============================================================


@router.post(
    "/purchase-orders/{po_number}/transition",
    response_model=PurchaseOrderResponse,
)
def transition_po(
    po_number: str,
    transition: PurchaseOrderTransition,
    user=Depends(
        require_roles("procurement_manager")
    ),
):
    """
    Transition a Purchase Order to another lifecycle state.

    Authorization:
        - procurement_manager -> allowed
        - supplier -> forbidden
        - all other roles -> forbidden

    The authenticated user's email is used as the transition
    actor. The client cannot impersonate another actor by
    supplying a different actor value in the request body.
    """

    # --------------------------------------------------------
    # Get authenticated actor
    # --------------------------------------------------------

    actor = user.get("email")

    if not actor:
        raise HTTPException(
            status_code=500,
            detail="Authenticated user identity is missing",
        )

    # --------------------------------------------------------
    # Perform Purchase Order transition
    # --------------------------------------------------------

    try:
        purchase_order = transition_purchase_order(
            po_number,
            actor,
            transition.target_state,
        )

        # ----------------------------------------------------
        # Purchase Order not found
        # ----------------------------------------------------

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
