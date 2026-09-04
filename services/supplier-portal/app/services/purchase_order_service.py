from datetime import datetime, date

from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderUpdate,
    PurchaseOrderStatus,
)

# In-memory po storage
purchase_orders = {}

# In-memory event storage
po_events =  {}


def create_purchase_order(
    purchase_order: PurchaseOrderCreate,
):
    """
    Create a new Purchase Order.
    """

    if purchase_order.po_number in purchase_orders:
        raise ValueError(
            "Purchase Order already exists."
        )

    # Calculate total from PO items
    calculated_total = sum(
        item.quantity * item.unit_price
        for item in purchase_order.items
    )

    calculated_total = round(
        calculated_total,
        2,
    )

    submitted_total = round(
        purchase_order.total_amount,
        2,
    )

    # Validate total amount
    if submitted_total != calculated_total:
        raise ValueError(
            "Purchase Order total amount does not "
            "match the item total. "
            f"Expected: {calculated_total:.2f}, "
            f"Received: {submitted_total:.2f}."
        )

    purchase_order_data = purchase_order.model_dump()

    purchase_order_data["status"] = (
        PurchaseOrderStatus.draft
    )

    purchase_order_data["history"] = []

    purchase_order_data["actual_delivery_date"] = None

    purchase_orders[
        purchase_order.po_number
    ] = purchase_order_data

    po_events[
        purchase_order.po_number
    ] = []

    return purchase_order_data

def get_purchase_order_events(po_number: str):
    """
    Return all events for a Purchase Order.
    """

    if po_number not in po_events:
        return None

    return po_events[po_number]


def get_purchase_order_by_id(po_number: str):
    """
    Get Purchase Order by PO Number.
    """

    return purchase_orders.get(po_number)

def get_all_purchase_orders():
    """
    Return all Purchase Orders.
    """
    return list(purchase_orders.values())


def update_purchase_order(
    po_number: str,
    purchase_order: PurchaseOrderUpdate,
):
    """
    Update an existing Purchase Order.

    Rules:
    - PO must exist.
    - Only draft POs can be updated.
    - If items or total_amount are changed, the total
      must match the sum of item quantities × unit prices.
    """

    # Check whether PO exists
    if po_number not in purchase_orders:
        return None

    existing_po = purchase_orders[po_number]

    # Only draft POs can be updated
    if existing_po["status"] != PurchaseOrderStatus.draft:
        raise ValueError(
            f"Purchase Order '{po_number}' cannot be updated "
            f"because its current status is "
            f"'{existing_po['status'].value}'. "
            "Only draft Purchase Orders can be updated."
        )

    # Get only fields provided by the client
    update_data = purchase_order.model_dump(
        exclude_unset=True
    )

    # Prevent empty update requests
    if not update_data:
        raise ValueError(
            "No fields were provided for update."
        )

    # Validate total when items or total_amount change
    if "items" in update_data or "total_amount" in update_data:

        items = update_data.get(
            "items",
            existing_po["items"],
        )

        total_amount = update_data.get(
            "total_amount",
            existing_po["total_amount"],
        )

        # Calculate total from items
        calculated_total = sum(
            item["quantity"] * item["unit_price"]
            for item in items
        )

        calculated_total = round(
            calculated_total,
            2,
        )

        submitted_total = round(
            total_amount,
            2,
        )

        # Validate total
        if submitted_total != calculated_total:
            raise ValueError(
                "Purchase Order total amount does not "
                "match the item total. "
                f"Expected: {calculated_total:.2f}, "
                f"Received: {submitted_total:.2f}."
            )

    # Apply validated changes
    existing_po.update(update_data)

    # Save updated PO
    purchase_orders[po_number] = existing_po

    return existing_po

def delete_purchase_order(po_number: str):
    if po_number not in purchase_orders:
        return False

    del purchase_orders[po_number]

    return True


def acknowledge_purchase_order(po_number: str):
    """
    Acknowledge an existing Purchase Order
    using the state machine.
    """

    return transition_purchase_order(
        po_number,
        "supplier",
        PurchaseOrderStatus.acknowledged,
    )

# valid transitions and history tracking



VALID_TRANSITIONS = {
    PurchaseOrderStatus.draft: [
        PurchaseOrderStatus.sent,
        PurchaseOrderStatus.cancelled,
    ],
    PurchaseOrderStatus.sent: [
        PurchaseOrderStatus.acknowledged,
        PurchaseOrderStatus.cancelled,
    ],
    PurchaseOrderStatus.acknowledged: [
        PurchaseOrderStatus.fulfilled,
        PurchaseOrderStatus.cancelled,
    ],
    PurchaseOrderStatus.fulfilled: [],
    PurchaseOrderStatus.cancelled: [],
}


def transition_purchase_order(
    po_number: str,
    actor: str,
    target_state: PurchaseOrderStatus,
):
    """
    Change Purchase Order status using the state machine
    and store the transition history with a timestamp.
    """

    # Check whether the Purchase Order exists
    if po_number not in purchase_orders:
        return None

    purchase_order = purchase_orders[po_number]

    # Current status
    current_state = purchase_order["status"]

    # Allowed transitions
    allowed_states = VALID_TRANSITIONS[current_state]

    # Check whether the transition is legal
    if target_state not in allowed_states:

        allowed = ", ".join(
            state.value for state in allowed_states
        )

        if not allowed:
            allowed = "none"

        raise ValueError(
            f"Cannot go from {current_state.value} "
            f"to {target_state.value}. "
            f"Allowed: {allowed}."
        )

    # Set actual delivery date when PO is fulfilled
    if target_state == PurchaseOrderStatus.fulfilled:
        purchase_order["actual_delivery_date"] = date.today()

    # Create audit event
    event = {
        "actor": actor,
        "from_status": current_state,
        "to_status": target_state,
        "timestamp": datetime.now().isoformat(),
    }

    # Store the event in ONE place only.
    # po_events is the single source of truth for audit history.
    po_events.setdefault(po_number, []).append(event)

    # Update status
    purchase_order["status"] = target_state

    # Get history from the single event store
    purchase_order["history"] = po_events.get(
        po_number,
        []
    )

    # Save Purchase Order
    purchase_orders[po_number] = purchase_order

    return purchase_order


def bulk_send_purchase_orders(po_numbers: list[str],  actor: str,):
    """
    Send multiple Purchase Orders from draft -> sent.

    Each PO is processed independently.

    Success:
        draft -> sent

    Failure:
        PO does not exist
        OR PO is not in draft status

    One failed PO does not stop the remaining POs.
    """

    results = []

    successful = 0
    failed = 0

    for po_number in po_numbers:

        # ----------------------------------------------------
        # 1. Check whether PO exists
        # ----------------------------------------------------

        if po_number not in purchase_orders:

            results.append({
                "po_number": po_number,
                "success": False,
                "status": None,
                "error": "Purchase Order not found",
            })

            failed += 1
            continue

        # ----------------------------------------------------
        # 2. Use the existing state-machine function
        # ----------------------------------------------------

        try:

            purchase_order = transition_purchase_order(
                po_number=po_number,
                actor=actor,
                target_state=PurchaseOrderStatus.sent,
            )

            # ------------------------------------------------
            # 3. Successful result
            # ------------------------------------------------

            results.append({
                "po_number": po_number,
                "success": True,
                "status": purchase_order["status"],
                "error": None,
            })

            successful += 1

        except ValueError as e:

            # ------------------------------------------------
            # 4. One PO failure should not stop the batch
            # ------------------------------------------------

            current_status = (
                purchase_orders[po_number]["status"]
            )

            results.append({
                "po_number": po_number,
                "success": False,
                "status": current_status,
                "error": str(e),
            })

            failed += 1

    # --------------------------------------------------------
    # 5. Return complete bulk result
    # --------------------------------------------------------

    return {
        "total": len(po_numbers),
        "successful": successful,
        "failed": failed,
        "results": results,
    }