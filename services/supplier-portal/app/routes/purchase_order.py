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

def require_po_access(supplier_only: bool = False):
    """
    Purchase Order access guard.

    supplier_only=False:
        Suppliers can access only their own POs.
        Internal roles can access any PO.

    supplier_only=True:
        Only the owning supplier can perform the action.
        Internal roles are not allowed.
    """

    def dependency(
        po_number: str,
        user=Depends(verify_token),
    ):
        # 1. Supplier access
        if user.get("role") == "supplier":
            authenticated_supplier_id = user.get("supplier_id")

            if not authenticated_supplier_id:
                raise HTTPException(
                    status_code=403,
                    detail="Supplier identity is missing",
                )

        # 2. Supplier-only action
        elif supplier_only:
            raise HTTPException(
                status_code=403,
                detail="Forbidden: supplier access required",
            )

        # 3. Find Purchase Order
        purchase_order = get_purchase_order_by_id(po_number)

        if not purchase_order:
            raise HTTPException(
                status_code=404,
                detail="Purchase Order not found",
            )

        # 4. Supplier scoping
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



def require_po_event_access(
    po_number: str,
    user=Depends(verify_token),
):
    """
    Authorize access to Purchase Order audit history.

    Internal users can view any PO event history.
    Suppliers can view only their own PO event history.
    Event history remains available even after the PO is deleted.
    """

    # --------------------------------------------------------
    # 1. Get authenticated supplier identity
    # --------------------------------------------------------

    authenticated_supplier_id = user.get("supplier_id")

    # Suppliers must have a supplier_id.
    # This check must happen before looking up the PO/events
    # so a supplier without identity receives 403, not 404.
    if user.get("role") == "supplier" and not authenticated_supplier_id:
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
    # 4. PO was deleted
    #
    # Use preserved audit events to verify supplier ownership.
    # Internal users can still view the history.
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
        and authenticated_supplier_id not in event_supplier_ids
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
# Supplier-facing endpoint
# Requires: supplier role + supplier_id scoping
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
        - procurement_manager → allowed
        - supplier → forbidden
        - all other roles → forbidden

    Authentication and role validation are handled by
    require_roles(), which calls the Platform Service
    authentication flow.
    """

    try:
        return create_purchase_order(
            purchase_order
        )

    except ValueError as e:
        message = str(e)

        # ----------------------------------------------------
        # Duplicate PO → 409 Conflict
        # ----------------------------------------------------

        if "already exists" in message:
            raise HTTPException(
                status_code=409,
                detail=message,
            )

        # ----------------------------------------------------
        # Invalid business data → 400 Bad Request
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
def list_purchase_orders(
    user=Depends(verify_token),
):
    """
    Get Purchase Orders.

    Supplier:
        Returns only Purchase Orders belonging to the
        authenticated supplier.

    Internal users:
        Returns all Purchase Orders.

    Supplier scoping rule:
        A supplier can only see POs where the PO supplier_id
        matches the supplier_id from the authenticated token.
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
# Supplier-facing endpoint
# Requires: supplier role + supplier_id scoping
# ============================================================

@router.get(
    "/purchase-orders/{po_number}",
    response_model=PurchaseOrderResponse,
)
def get_purchase_order(
    access=Depends(require_po_access()),
):

    user, purchase_order = access

    return purchase_order


# ============================================================
# UPDATE PURCHASE ORDER
# Requires authentication + role-based authorization
#
# Supplier:
#   Can update only their own Purchase Orders.
#
# Procurement Manager:
#   Can update any Purchase Order.
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
    user=Depends(verify_token),
):
    """
    Update a Purchase Order.

    Authorization rules:

    1. User must be authenticated.
    2. Supplier users can update only their own PO.
    3. Procurement managers can update any PO.
    4. All other roles are forbidden.

    Supplier ownership is determined using the supplier_id
    returned by the authenticated Platform Service token.
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
# Requires authentication + role-based authorization
#
# Supplier:
#   Can delete only their own Purchase Orders.
#
# Procurement Manager:
#   Can delete any Purchase Order.
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
    user=Depends(verify_token),
):
    """
    Delete a Purchase Order.

    Authorization rules:

    1. User must be authenticated.
    2. Supplier users can delete only their own PO.
    3. Procurement managers can delete any PO.
    4. All other roles are forbidden.

    Supplier ownership is determined using the supplier_id
    returned by the authenticated Platform Service token.
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

        # Supplier token must contain supplier identity
        if not authenticated_supplier_id:
            raise HTTPException(
                status_code=403,
                detail="Supplier identity is missing",
            )

        # Supplier can delete only their own PO
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
# Supplier-facing endpoint
# Requires: supplier role + supplier_id scoping
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
# The transition actor is taken from the authenticated user,
# not from the request body.
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
        - procurement_manager → allowed
        - supplier → forbidden
        - all other roles → forbidden

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
