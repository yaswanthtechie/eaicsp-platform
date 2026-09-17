import pytest

from app.services.po_p2p_state_machine import (
    P2PState,
    P2P_TRANSITIONS,
    p2p_states,
    initialize_p2p_state,
    get_p2p_state,
    can_transition_p2p,
    transition_p2p,
    remove_p2p_state,
)


# ============================================================
# TEST CLEANUP
# ============================================================

@pytest.fixture(autouse=True)
def clear_p2p_states():
    """
    Clear the in-memory P2P state before and after every test.

    This prevents one test from affecting another test.
    """

    p2p_states.clear()

    yield

    p2p_states.clear()


# ============================================================
# INITIALIZATION TESTS
# ============================================================


def test_initialize_p2p_state():
    """
    A Purchase Order can be initialized at acknowledged state.
    """

    result = initialize_p2p_state(
        "PO1001",
        P2PState.acknowledged,
    )

    assert result == P2PState.acknowledged
    assert get_p2p_state("PO1001") == P2PState.acknowledged


def test_get_p2p_state_for_unknown_po_returns_none():
    """
    An unknown Purchase Order has no P2P state.
    """

    assert get_p2p_state("PO9999") is None


# ============================================================
# LEGAL TRANSITION TESTS
# ============================================================


def test_acknowledged_to_shipped_is_legal():
    initialize_p2p_state(
        "PO1001",
        P2PState.acknowledged,
    )

    assert can_transition_p2p(
        "PO1001",
        P2PState.shipped,
    ) is True

    result = transition_p2p(
        "PO1001",
        P2PState.shipped,
    )

    assert result == P2PState.shipped
    assert get_p2p_state("PO1001") == P2PState.shipped


def test_shipped_to_received_is_legal():
    initialize_p2p_state(
        "PO1001",
        P2PState.shipped,
    )

    assert can_transition_p2p(
        "PO1001",
        P2PState.received,
    ) is True

    result = transition_p2p(
        "PO1001",
        P2PState.received,
    )

    assert result == P2PState.received
    assert get_p2p_state("PO1001") == P2PState.received


def test_received_to_invoiced_is_legal():
    initialize_p2p_state(
        "PO1001",
        P2PState.received,
    )

    assert can_transition_p2p(
        "PO1001",
        P2PState.invoiced,
    ) is True

    result = transition_p2p(
        "PO1001",
        P2PState.invoiced,
    )

    assert result == P2PState.invoiced
    assert get_p2p_state("PO1001") == P2PState.invoiced


def test_invoiced_to_matched_is_legal():
    initialize_p2p_state(
        "PO1001",
        P2PState.invoiced,
    )

    assert can_transition_p2p(
        "PO1001",
        P2PState.matched,
    ) is True

    result = transition_p2p(
        "PO1001",
        P2PState.matched,
    )

    assert result == P2PState.matched
    assert get_p2p_state("PO1001") == P2PState.matched


def test_invoiced_to_discrepancy_is_legal():
    initialize_p2p_state(
        "PO1001",
        P2PState.invoiced,
    )

    assert can_transition_p2p(
        "PO1001",
        P2PState.discrepancy,
    ) is True

    result = transition_p2p(
        "PO1001",
        P2PState.discrepancy,
    )

    assert result == P2PState.discrepancy
    assert get_p2p_state("PO1001") == P2PState.discrepancy


def test_discrepancy_to_matched_is_legal():
    initialize_p2p_state(
        "PO1001",
        P2PState.discrepancy,
    )

    assert can_transition_p2p(
        "PO1001",
        P2PState.matched,
    ) is True

    result = transition_p2p(
        "PO1001",
        P2PState.matched,
    )

    assert result == P2PState.matched
    assert get_p2p_state("PO1001") == P2PState.matched


def test_matched_to_payment_approved_is_legal():
    initialize_p2p_state(
        "PO1001",
        P2PState.matched,
    )

    assert can_transition_p2p(
        "PO1001",
        P2PState.payment_approved,
    ) is True

    result = transition_p2p(
        "PO1001",
        P2PState.payment_approved,
    )

    assert result == P2PState.payment_approved
    assert get_p2p_state("PO1001") == P2PState.payment_approved


# ============================================================
# ILLEGAL TRANSITION TESTS
# ============================================================


def test_acknowledged_to_received_is_illegal():
    initialize_p2p_state(
        "PO1001",
        P2PState.acknowledged,
    )

    assert can_transition_p2p(
        "PO1001",
        P2PState.received,
    ) is False

    with pytest.raises(ValueError, match="Cannot move"):
        transition_p2p(
            "PO1001",
            P2PState.received,
        )


def test_acknowledged_to_invoiced_is_illegal():
    initialize_p2p_state(
        "PO1001",
        P2PState.acknowledged,
    )

    assert can_transition_p2p(
        "PO1001",
        P2PState.invoiced,
    ) is False

    with pytest.raises(ValueError, match="Cannot move"):
        transition_p2p(
            "PO1001",
            P2PState.invoiced,
        )


def test_acknowledged_to_matched_is_illegal():
    initialize_p2p_state(
        "PO1001",
        P2PState.acknowledged,
    )

    assert can_transition_p2p(
        "PO1001",
        P2PState.matched,
    ) is False

    with pytest.raises(ValueError, match="Cannot move"):
        transition_p2p(
            "PO1001",
            P2PState.matched,
        )


def test_acknowledged_to_payment_approved_is_illegal():
    initialize_p2p_state(
        "PO1001",
        P2PState.acknowledged,
    )

    assert can_transition_p2p(
        "PO1001",
        P2PState.payment_approved,
    ) is False

    with pytest.raises(ValueError, match="Cannot move"):
        transition_p2p(
            "PO1001",
            P2PState.payment_approved,
        )


def test_shipped_to_invoiced_is_illegal():
    initialize_p2p_state(
        "PO1001",
        P2PState.shipped,
    )

    assert can_transition_p2p(
        "PO1001",
        P2PState.invoiced,
    ) is False

    with pytest.raises(ValueError, match="Cannot move"):
        transition_p2p(
            "PO1001",
            P2PState.invoiced,
        )


def test_shipped_to_matched_is_illegal():
    initialize_p2p_state(
        "PO1001",
        P2PState.shipped,
    )

    assert can_transition_p2p(
        "PO1001",
        P2PState.matched,
    ) is False

    with pytest.raises(ValueError, match="Cannot move"):
        transition_p2p(
            "PO1001",
            P2PState.matched,
        )


def test_shipped_to_payment_approved_is_illegal():
    initialize_p2p_state(
        "PO1001",
        P2PState.shipped,
    )

    assert can_transition_p2p(
        "PO1001",
        P2PState.payment_approved,
    ) is False

    with pytest.raises(ValueError, match="Cannot move"):
        transition_p2p(
            "PO1001",
            P2PState.payment_approved,
        )


def test_received_to_matched_is_illegal():
    initialize_p2p_state(
        "PO1001",
        P2PState.received,
    )

    assert can_transition_p2p(
        "PO1001",
        P2PState.matched,
    ) is False

    with pytest.raises(ValueError, match="Cannot move"):
        transition_p2p(
            "PO1001",
            P2PState.matched,
        )


def test_received_to_payment_approved_is_illegal():
    initialize_p2p_state(
        "PO1001",
        P2PState.received,
    )

    assert can_transition_p2p(
        "PO1001",
        P2PState.payment_approved,
    ) is False

    with pytest.raises(ValueError, match="Cannot move"):
        transition_p2p(
            "PO1001",
            P2PState.payment_approved,
        )


def test_invoiced_to_payment_approved_is_illegal():
    initialize_p2p_state(
        "PO1001",
        P2PState.invoiced,
    )

    assert can_transition_p2p(
        "PO1001",
        P2PState.payment_approved,
    ) is False

    with pytest.raises(ValueError, match="Cannot move"):
        transition_p2p(
            "PO1001",
            P2PState.payment_approved,
        )


def test_discrepancy_to_payment_approved_is_illegal():
    """
    Payment must never bypass discrepancy resolution.
    """

    initialize_p2p_state(
        "PO1001",
        P2PState.discrepancy,
    )

    assert can_transition_p2p(
        "PO1001",
        P2PState.payment_approved,
    ) is False

    with pytest.raises(ValueError, match="Cannot move"):
        transition_p2p(
            "PO1001",
            P2PState.payment_approved,
        )


def test_payment_approved_to_any_state_is_illegal():
    """
    payment_approved is a terminal P2P state.
    """

    initialize_p2p_state(
        "PO1001",
        P2PState.payment_approved,
    )

    for target_state in P2PState:

        assert can_transition_p2p(
            "PO1001",
            target_state,
        ) is False

        with pytest.raises(ValueError, match="Cannot move"):
            transition_p2p(
                "PO1001",
                target_state,
            )


# ============================================================
# UNINITIALIZED PO TESTS
# ============================================================


def test_uninitialized_po_cannot_transition():
    """
    A PO without a P2P workflow state cannot transition.
    """

    assert can_transition_p2p(
        "PO9999",
        P2PState.shipped,
    ) is False

    with pytest.raises(
        ValueError,
        match="P2P workflow state not initialized",
    ):
        transition_p2p(
            "PO9999",
            P2PState.shipped,
        )


# ============================================================
# STATE PERSISTENCE TEST
# ============================================================


def test_transition_updates_current_state():
    initialize_p2p_state(
        "PO1001",
        P2PState.acknowledged,
    )

    transition_p2p(
        "PO1001",
        P2PState.shipped,
    )

    assert get_p2p_state("PO1001") == P2PState.shipped

    transition_p2p(
        "PO1001",
        P2PState.received,
    )

    assert get_p2p_state("PO1001") == P2PState.received


# ============================================================
# FULL LEGAL P2P FLOW TEST
# ============================================================


def test_complete_p2p_happy_path():
    """
    Verify the complete legal P2P workflow.
    """

    initialize_p2p_state(
        "PO1001",
        P2PState.acknowledged,
    )

    transition_p2p(
        "PO1001",
        P2PState.shipped,
    )

    transition_p2p(
        "PO1001",
        P2PState.received,
    )

    transition_p2p(
        "PO1001",
        P2PState.invoiced,
    )

    transition_p2p(
        "PO1001",
        P2PState.matched,
    )

    transition_p2p(
        "PO1001",
        P2PState.payment_approved,
    )

    assert get_p2p_state(
        "PO1001"
    ) == P2PState.payment_approved


# ============================================================
# FULL DISCREPANCY FLOW TEST
# ============================================================


def test_complete_p2p_discrepancy_resolution_flow():
    """
    Verify:

    acknowledged
        -> shipped
        -> received
        -> invoiced
        -> discrepancy
        -> matched
        -> payment_approved
    """

    initialize_p2p_state(
        "PO1001",
        P2PState.acknowledged,
    )

    transition_p2p(
        "PO1001",
        P2PState.shipped,
    )

    transition_p2p(
        "PO1001",
        P2PState.received,
    )

    transition_p2p(
        "PO1001",
        P2PState.invoiced,
    )

    transition_p2p(
        "PO1001",
        P2PState.discrepancy,
    )

    # Payment must remain blocked.
    assert can_transition_p2p(
        "PO1001",
        P2PState.payment_approved,
    ) is False

    # Human resolution moves discrepancy -> matched.
    transition_p2p(
        "PO1001",
        P2PState.matched,
    )

    # Payment can now proceed.
    transition_p2p(
        "PO1001",
        P2PState.payment_approved,
    )

    assert get_p2p_state(
        "PO1001"
    ) == P2PState.payment_approved


# ============================================================
# STATE MACHINE TABLE CONSISTENCY TEST
# ============================================================


def test_every_state_has_defined_transition_rule():
    """
    Every P2P state must have an explicit transition definition.
    """

    for state in P2PState:
        assert state in P2P_TRANSITIONS


# ============================================================
# P2P STATE CLEANUP TEST
# ============================================================


def test_remove_p2p_state():
    """
    Removing a Purchase Order also removes its P2P workflow state.
    """

    initialize_p2p_state(
        "PO1001",
        P2PState.acknowledged,
    )

    assert get_p2p_state("PO1001") == P2PState.acknowledged

    remove_p2p_state("PO1001")

    assert get_p2p_state("PO1001") is None