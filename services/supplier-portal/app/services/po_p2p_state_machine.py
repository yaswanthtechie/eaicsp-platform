from enum import Enum


class P2PState(str, Enum):
    """
    Shared procure-to-pay workflow state.

    This state represents the overall P2P progress of a
    Purchase Order across Shipment, Goods Receipt, Invoice,
    Three-Way Match and Payment.
    """

    acknowledged = "acknowledged"
    shipped = "shipped"
    received = "received"
    invoiced = "invoiced"
    matched = "matched"
    discrepancy = "discrepancy"
    payment_approved = "payment_approved"


# ============================================================
# LEGAL P2P TRANSITIONS
# ============================================================

P2P_TRANSITIONS = {
    P2PState.acknowledged: [
        P2PState.shipped,
    ],

    P2PState.shipped: [
        P2PState.received,
    ],

    P2PState.received: [
        P2PState.invoiced,
    ],

    P2PState.invoiced: [
        P2PState.matched,
        P2PState.discrepancy,
    ],

    P2PState.matched: [
        P2PState.payment_approved,
    ],

    P2PState.discrepancy: [
        P2PState.matched,
    ],

    P2PState.payment_approved: [],
}


# ============================================================
# IN-MEMORY P2P STATE
# ============================================================

p2p_states: dict[str, P2PState] = {}


def initialize_p2p_state(
    po_number: str,
    state: P2PState,
) -> P2PState:
    """
    Initialize the P2P workflow state for a Purchase Order.

    This should normally happen when a PO reaches the
    acknowledged stage.
    """

    p2p_states[po_number] = state

    return state


def get_p2p_state(
    po_number: str,
) -> P2PState | None:
    """
    Return the current P2P workflow state for a PO.
    """

    return p2p_states.get(po_number)


def can_transition_p2p(
    po_number: str,
    target_state: P2PState,
) -> bool:
    """
    Check whether the requested P2P transition is legal.
    """

    current_state = get_p2p_state(po_number)

    if current_state is None:
        return False

    allowed_states = P2P_TRANSITIONS.get(
        current_state,
        [],
    )

    return target_state in allowed_states


def transition_p2p(
    po_number: str,
    target_state: P2PState,
) -> P2PState:
    """
    Perform a legal P2P state transition.

    Every P2P module must use this function before
    advancing the Purchase Order workflow.
    """

    current_state = get_p2p_state(po_number)

    if current_state is None:
        raise ValueError(
            f"P2P workflow state not initialized for "
            f"Purchase Order '{po_number}'."
        )

    allowed_states = P2P_TRANSITIONS.get(
        current_state,
        [],
    )

    if target_state not in allowed_states:

        allowed = ", ".join(
            state.value
            for state in allowed_states
        )

        if not allowed:
            allowed = "none"

        raise ValueError(
            f"Cannot move Purchase Order '{po_number}' "
            f"from P2P state '{current_state.value}' "
            f"to '{target_state.value}'. "
            f"Allowed: {allowed}."
        )

    p2p_states[po_number] = target_state

    return target_state


def remove_p2p_state(
    po_number: str,
) -> None:
    """
    Remove P2P state when a Purchase Order is permanently
    removed from in-memory storage.
    """

    p2p_states.pop(
        po_number,
        None,
    )