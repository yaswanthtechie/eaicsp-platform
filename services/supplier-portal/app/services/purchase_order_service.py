from datetime import datetime, date

from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderUpdate,
    PurchaseOrderStatus,
)

# In-memory po storage
purchase_orders = {}

# In-memory event storage
po_events = []



def create_purchase_order(purchase_order: PurchaseOrderCreate):
    """
    Create a new Purchase Order.
    """

    if purchase_order.po_number in purchase_orders:
        raise ValueError("Purchase Order already exists.")

    purchase_order_data = purchase_order.model_dump()

    # Every new Purchase Order starts in draft state
    purchase_order_data["status"] = PurchaseOrderStatus.draft

# Initialize history
    purchase_order_data["history"] = []

    purchase_order_data["actual_delivery_date"] = None

    purchase_orders[purchase_order.po_number] = purchase_order_data

    return purchase_order_data


def get_all_purchase_orders():
    """
    Return all Purchase Orders.
    """

    return list(purchase_orders.values())


def get_purchase_order_by_id(po_number: str):
    """
    Get Purchase Order by PO Number.
    """

    return purchase_orders.get(po_number)


def update_purchase_order(
    po_number: str,
    purchase_order: PurchaseOrderUpdate
):
    """
    Update an existing Purchase Order.
    """

    if po_number not in purchase_orders:
        return None

    existing_po = purchase_orders[po_number]

    update_data = purchase_order.model_dump(exclude_unset=True)

    existing_po.update(update_data)

    purchase_orders[po_number] = existing_po

    return existing_po


def delete_purchase_order(po_number: str):
    """
    Delete a Purchase Order.
    """

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
            f"Allowed transitions: {allowed}."
        )

    # Create history if it does not exist
    if "history" not in purchase_order:
        purchase_order["history"] = []


    if target_state == PurchaseOrderStatus.sent:
        actor = "procurement"

    elif target_state == PurchaseOrderStatus.acknowledged:
        actor = "supplier"

    elif target_state == PurchaseOrderStatus.fulfilled:
        actor = "logistics"

        purchase_order["actual_delivery_date"] = (
        date.today()
    )

    elif target_state == PurchaseOrderStatus.cancelled:
        actor = "admin"


    # Create event
    event = {
        "actor": actor, 
        "from_status": current_state,
        "to_status": target_state,
        "timestamp": datetime.now(),
    }

    # Save history
    purchase_order["history"].append(event)

    # Save event log,
    po_events.append(
        {
            "po_number": po_number,
            **event,
        }
    )

    # Update status
    purchase_order["status"] = target_state

    # Save Purchase Order
    purchase_orders[po_number] = purchase_order

    return purchase_order