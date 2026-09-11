import pytest

from app.services.purchase_order_service import (
    purchase_orders,
    po_events,
)
from app.services.invoice_service import invoices


# ============================================================
# TEST SETUP
# ============================================================

def setup_function():
    """
    Clear all in-memory stores before every test.
    """
    purchase_orders.clear()
    invoices.clear()
    po_events.clear()


# ============================================================
# TEST DATA HELPERS
# ============================================================

def create_sample_po(
    client,
    po_number="PO1001",
    supplier_id="SUP001",
):
    """
    Create a valid Purchase Order.

    PO creation is an internal procurement operation,
    therefore this helper must receive procurement_client.
    """

    response = client.post(
        "/api/v1/purchase-orders",
        json={
            "po_number": po_number,
            "supplier_id": supplier_id,
            "items": [
                {
                    "item_code": "LAP001",
                    "description": "Laptop",
                    "quantity": 10,
                    "unit_price": 5000,
                },
                {
                    "item_code": "MOU001",
                    "description": "Wireless Mouse",
                    "quantity": 10,
                    "unit_price": 500,
                },
            ],
            "total_amount": 55000,
            "created_at": "2026-07-23T10:00:00",
            "expected_delivery": "2026-07-30",
        },
    )

    assert response.status_code == 201, response.text

    return response


def send_po(
    procurement_client,
    po_number="PO1001",
):
    """
    draft -> sent

    Only procurement manager can perform this transition.
    """

    response = procurement_client.post(
        f"/api/v1/purchase-orders/{po_number}/transition",
        json={
            "actor": "harish",
            "target_state": "sent",
        },
    )

    return response


def acknowledge_po(
    supplier_client,
    po_number="PO1001",
):
    """
    sent -> acknowledged

    Supplier performs the acknowledgement.

    supplier_client must represent the supplier that owns
    the Purchase Order.
    """

    response = supplier_client.post(
        f"/api/v1/purchase-orders/{po_number}/acknowledge"
    )

    return response


def fulfill_po(
    procurement_client,
    po_number="PO1001",
):
    """
    acknowledged -> fulfilled

    Only procurement manager can perform this transition.
    """

    response = procurement_client.post(
        f"/api/v1/purchase-orders/{po_number}/transition",
        json={
            "actor": "dhanush",
            "target_state": "fulfilled",
        },
    )

    return response


def cancel_po(
    procurement_client,
    po_number="PO1001",
    actor="siri",
):
    """
    Move PO to cancelled state.

    Cancellation is a procurement operation.
    """

    response = procurement_client.post(
        f"/api/v1/purchase-orders/{po_number}/transition",
        json={
            "actor": actor,
            "target_state": "cancelled",
        },
    )

    return response

# ============================================================
# CREATE / READ / UPDATE / DELETE
# ============================================================

def test_create_purchase_order(procurement_client):

    response = create_sample_po(procurement_client)

    body = response.json()

    assert response.status_code == 201
    assert body["po_number"] == "PO1001"
    assert body["supplier_id"] == "SUP001"
    assert body["status"] == "draft"
    assert body["total_amount"] == 55000
    assert body["actual_delivery_date"] is None
    assert body["history"] == []


def test_duplicate_purchase_order(procurement_client):

    # First PO creation should succeed
    response = create_sample_po(procurement_client)

    assert response.status_code == 201

    # Second creation with same PO number
    response = procurement_client.post(
        "/api/v1/purchase-orders",
        json={
            "po_number": "PO1001",
            "supplier_id": "SUP001",
            "items": [
                {
                    "item_code": "LAP001",
                    "description": "Laptop",
                    "quantity": 10,
                    "unit_price": 5000,
                },
                {
                    "item_code": "MOU001",
                    "description": "Wireless Mouse",
                    "quantity": 10,
                    "unit_price": 500,
                },
            ],
            "total_amount": 55000,
            "created_at": "2026-07-23T10:00:00",
            "expected_delivery": "2026-07-30",
        },
    )

    assert response.status_code == 409

    body = response.json()

    assert "already exists" in body["detail"]


def test_create_purchase_order_wrong_total(procurement_client):

    response = procurement_client.post(
        "/api/v1/purchase-orders",
        json={
            "po_number": "PO1002",
            "supplier_id": "SUP001",
            "items": [
                {
                    "item_code": "LAP001",
                    "description": "Laptop",
                    "quantity": 10,
                    "unit_price": 5000,
                }
            ],
            "total_amount": 60000,
            "created_at": "2026-07-23T10:00:00",
            "expected_delivery": "2026-07-30",
        },
    )

    assert response.status_code == 400

    assert (
        "does not match the item total"
        in response.json()["detail"]
    )


def test_get_all_purchase_orders(procurement_client):

    create_sample_po(procurement_client)

    response = procurement_client.get(
        "/api/v1/purchase-orders"
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1
    assert body[0]["po_number"] == "PO1001"


def test_get_purchase_order_by_id(
    procurement_client,
    supplier_client,
):

    create_sample_po(procurement_client)

    response = supplier_client.get(
        "/api/v1/purchase-orders/PO1001"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["po_number"] == "PO1001"


def test_get_purchase_order_not_found(supplier_client):

    response = supplier_client.get(
        "/api/v1/purchase-orders/PO9999"
    )

    assert response.status_code == 404

    assert (
        response.json()["detail"]
        == "Purchase Order not found"
    )


def test_update_purchase_order(procurement_client):

    create_sample_po(procurement_client)

    response = procurement_client.put(
        "/api/v1/purchase-orders/PO1001",
        json={
            "total_amount": 55000,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["po_number"] == "PO1001"
    assert body["total_amount"] == 55000


def test_delete_purchase_order(
    procurement_client,
    supplier_client,
):

    create_sample_po(procurement_client)

    response = procurement_client.delete(
        "/api/v1/purchase-orders/PO1001"
    )

    assert response.status_code == 200

    assert (
        "deleted successfully"
        in response.json()["message"]
    )

    response = supplier_client.get(
        "/api/v1/purchase-orders/PO1001"
    )

    assert response.status_code == 404


# ============================================================
# LEGAL STATE TRANSITIONS
# ============================================================


def test_draft_to_sent(procurement_client):
    """
    Verify that a procurement manager can transition
    a Purchase Order from draft -> sent.

    R5:
    The transition actor must be taken from the
    authenticated user's email, not the request body.
    """

    create_sample_po(procurement_client)

    response = send_po(procurement_client)

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "sent"

    assert len(body["history"]) == 1

    event = body["history"][0]

    assert event["from_status"] == "draft"
    assert event["to_status"] == "sent"

    # Authenticated procurement manager identity
    # must be recorded as the actor.
    assert event["actor"] == (
        "procurementmanager@company.com"
    )

    assert "timestamp" in event


def test_sent_to_acknowledged(
    procurement_client,
    supplier_client,
):
    """
    Verify that a supplier can acknowledge
    a Purchase Order after it has been sent.
    """

    create_sample_po(procurement_client)

    # draft -> sent
    response = send_po(procurement_client)

    assert response.status_code == 200

    # sent -> acknowledged
    response = acknowledge_po(supplier_client)

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "acknowledged"

    assert len(body["history"]) == 2

    event = body["history"][1]

    assert event["from_status"] == "sent"
    assert event["to_status"] == "acknowledged"

    # Supplier acknowledgement is recorded
    # using the supplier actor.
    assert event["actor"] == "supplier"

    assert "timestamp" in event


def test_acknowledged_to_fulfilled(
    procurement_client,
    supplier_client,
):
    """
    Verify that a procurement manager can transition
    an acknowledged Purchase Order to fulfilled.

    R5:
    The authenticated procurement manager's email
    must be recorded as the actor.
    """

    create_sample_po(procurement_client)

    # draft -> sent
    send_response = send_po(procurement_client)

    assert send_response.status_code == 200

    # sent -> acknowledged
    acknowledge_response = acknowledge_po(
        supplier_client
    )

    assert acknowledge_response.status_code == 200

    # acknowledged -> fulfilled
    response = fulfill_po(procurement_client)

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "fulfilled"

    assert len(body["history"]) == 3

    event = body["history"][2]

    assert event["from_status"] == "acknowledged"
    assert event["to_status"] == "fulfilled"

    # Actor must come from the authenticated
    # procurement manager, not the request body.
    assert event["actor"] == (
        "procurementmanager@company.com"
    )

    assert "timestamp" in event

    assert body["actual_delivery_date"] is not None


def test_draft_to_cancelled(procurement_client):
    """
    Verify that a procurement manager can transition
    a draft Purchase Order to cancelled.

    R5:
    The authenticated user's email is recorded
    as the transition actor.
    """

    create_sample_po(procurement_client)

    response = cancel_po(
        procurement_client,
        actor="siri",
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "cancelled"

    assert len(body["history"]) == 1

    event = body["history"][0]

    assert event["from_status"] == "draft"
    assert event["to_status"] == "cancelled"

    # The request-body actor "siri" must NOT be trusted.
    assert event["actor"] == (
        "procurementmanager@company.com"
    )

    assert event["actor"] != "siri"

    assert "timestamp" in event


def test_sent_to_cancelled(procurement_client):
    """
    Verify that a sent Purchase Order can be
    cancelled by the procurement manager.
    """

    create_sample_po(procurement_client)

    # draft -> sent
    response = send_po(procurement_client)

    assert response.status_code == 200

    # sent -> cancelled
    response = cancel_po(
        procurement_client,
        actor="siri",
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "cancelled"

    assert len(body["history"]) == 2

    event = body["history"][1]

    assert event["from_status"] == "sent"
    assert event["to_status"] == "cancelled"

    # Authenticated procurement manager is the actor.
    assert event["actor"] == (
        "procurementmanager@company.com"
    )

    assert event["actor"] != "siri"

    assert "timestamp" in event


def test_acknowledged_to_cancelled(
    procurement_client,
    supplier_client,
):
    """
    Verify that an acknowledged Purchase Order
    can be cancelled by the procurement manager.
    """

    create_sample_po(procurement_client)

    # draft -> sent
    send_response = send_po(procurement_client)

    assert send_response.status_code == 200

    # sent -> acknowledged
    acknowledge_response = acknowledge_po(
        supplier_client
    )

    assert acknowledge_response.status_code == 200

    # acknowledged -> cancelled
    response = cancel_po(
        procurement_client,
        actor="siri",
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "cancelled"

    assert len(body["history"]) == 3

    event = body["history"][2]

    assert event["from_status"] == "acknowledged"
    assert event["to_status"] == "cancelled"

    # Authenticated procurement manager is the actor.
    assert event["actor"] == (
        "procurementmanager@company.com"
    )

    assert event["actor"] != "siri"

    assert "timestamp" in event


# ============================================================
# ILLEGAL STATE TRANSITIONS
# ============================================================

@pytest.mark.parametrize(
    "from_state,target_state",
    [
        ("draft", "acknowledged"),
        ("draft", "fulfilled"),

        ("sent", "draft"),
        ("sent", "fulfilled"),

        ("acknowledged", "draft"),
        ("acknowledged", "sent"),

        ("fulfilled", "draft"),
        ("fulfilled", "sent"),
        ("fulfilled", "acknowledged"),
        ("fulfilled", "cancelled"),

        ("cancelled", "draft"),
        ("cancelled", "sent"),
        ("cancelled", "acknowledged"),
        ("cancelled", "fulfilled"),
    ],
)
def test_illegal_purchase_order_transitions(
    procurement_client,
    supplier_client,
    from_state,
    target_state,
):
    """
    Verify that every illegal PO state transition
    is rejected with HTTP 400.
    """

    create_sample_po(procurement_client)

    # --------------------------------------------------------
    # Move PO to required starting state
    # --------------------------------------------------------

    if from_state == "sent":

        response = send_po(procurement_client)

        assert response.status_code == 200

    elif from_state == "acknowledged":

        response = send_po(procurement_client)

        assert response.status_code == 200

        response = acknowledge_po(
            supplier_client
        )

        assert response.status_code == 200

    elif from_state == "fulfilled":

        response = send_po(procurement_client)

        assert response.status_code == 200

        response = acknowledge_po(
            supplier_client
        )

        assert response.status_code == 200

        response = fulfill_po(procurement_client)

        assert response.status_code == 200

    elif from_state == "cancelled":

        response = cancel_po(
            procurement_client,
            actor="siri",
        )

        assert response.status_code == 200

    # --------------------------------------------------------
    # Attempt illegal transition
    # --------------------------------------------------------

    response = procurement_client.post(
        "/api/v1/purchase-orders/PO1001/transition",
        json={
            "actor": "tester",
            "target_state": target_state,
        },
    )

    assert response.status_code == 400

    detail = response.json()["detail"]

    assert (
        f"Cannot go from {from_state} to {target_state}"
        in detail
    )


# ============================================================
# ACKNOWLEDGE ENDPOINT
# ============================================================

def test_acknowledge_without_sent_status(
    procurement_client,
    supplier_client,
):

    create_sample_po(procurement_client)

    response = acknowledge_po(
        supplier_client
    )

    assert response.status_code == 400

    assert (
        "Cannot go from draft to acknowledged"
        in response.json()["detail"]
    )


def test_acknowledge_fulfilled_po(
    procurement_client,
    supplier_client,
):

    create_sample_po(procurement_client)

    send_po(procurement_client)

    acknowledge_po(supplier_client)

    fulfill_po(procurement_client)

    response = acknowledge_po(
        supplier_client
    )

    assert response.status_code == 400

    assert (
        "Cannot go from fulfilled to acknowledged"
        in response.json()["detail"]
    )


# ============================================================
# MISSING PO TRANSITIONS
# ============================================================

def test_transition_purchase_order_not_found(
    procurement_client,
):

    response = procurement_client.post(
        "/api/v1/purchase-orders/PO9999/transition",
        json={
            "actor": "tester",
            "target_state": "sent",
        },
    )

    assert response.status_code == 404

    assert (
        response.json()["detail"]
        == "Purchase Order not found"
    )


def test_acknowledge_purchase_order_not_found(
    supplier_client,
):

    response = supplier_client.post(
        "/api/v1/purchase-orders/PO9999/acknowledge"
    )

    assert response.status_code == 404

    assert (
        response.json()["detail"]
        == "Purchase Order not found"
    )


# ============================================================
# EVENT / HISTORY TESTS
# ============================================================

def test_purchase_order_events_empty(
    procurement_client,
    supplier_client,
):

    create_sample_po(procurement_client)

    response = supplier_client.get(
        "/api/v1/purchase-orders/PO1001/events"
    )

    assert response.status_code == 200

    assert response.json() == []


def test_purchase_order_events(
    procurement_client,
    supplier_client,
):

    create_sample_po(procurement_client)

    send_po(procurement_client)

    acknowledge_po(supplier_client)

    response = supplier_client.get(
        "/api/v1/purchase-orders/PO1001/events"
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 2

    assert body[0]["actor"] == (
        "procurementmanager@company.com"
    )
    assert body[0]["actor"] != "harish"
    assert body[0]["from_status"] == "draft"
    assert body[0]["to_status"] == "sent"

    assert body[1]["actor"] == "supplier"
    assert body[1]["from_status"] == "sent"
    assert body[1]["to_status"] == "acknowledged"


def test_purchase_order_events_not_found(
    supplier_client,
):

    response = supplier_client.get(
        "/api/v1/purchase-orders/PO9999/events"
    )

    assert response.status_code == 404

    assert (
        response.json()["detail"]
        == "Purchase Order not found"
    )


def test_history_is_preserved_after_delete(
    procurement_client,
    supplier_client,
):

    create_sample_po(procurement_client)

    send_po(procurement_client)

    acknowledge_po(supplier_client)

    # Delete using internal procurement role
    response = procurement_client.delete(
        "/api/v1/purchase-orders/PO1001"
    )

    assert response.status_code == 200

    # PO itself is deleted.
    response = supplier_client.get(
        "/api/v1/purchase-orders/PO1001"
    )

    assert response.status_code == 404

    # Audit events remain.
    response = supplier_client.get(
        "/api/v1/purchase-orders/PO1001/events"
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 2


# ============================================================
# BULK SEND
# ============================================================

def test_bulk_send_purchase_orders(
    procurement_client,
):

    create_sample_po(
        procurement_client,
        "PO1001",
    )

    create_sample_po(
        procurement_client,
        "PO1002",
    )

    create_sample_po(
        procurement_client,
        "PO1003",
    )

    response = procurement_client.post(
        "/api/v1/purchase-orders/bulk-send",
        json={
            "po_numbers": [
                "PO1001",
                "PO1002",
                "PO9999",
            ],
            "actor": "harish",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 3
    assert body["successful"] == 2
    assert body["failed"] == 1

    results = body["results"]

    # PO1001
    assert results[0]["po_number"] == "PO1001"
    assert results[0]["success"] is True
    assert results[0]["status"] == "sent"
    assert results[0]["error"] is None

    # PO1002
    assert results[1]["po_number"] == "PO1002"
    assert results[1]["success"] is True
    assert results[1]["status"] == "sent"
    assert results[1]["error"] is None

    # PO9999
    assert results[2]["po_number"] == "PO9999"
    assert results[2]["success"] is False
    assert results[2]["status"] is None
    assert results[2]["error"] == "Purchase Order not found"


def test_bulk_send_only_draft_can_be_sent(
    procurement_client,
):

    create_sample_po(
        procurement_client,
        "PO1001",
    )

    create_sample_po(
        procurement_client,
        "PO1002",
    )

    # --------------------------------------------------------
    # First send PO1001 normally
    # draft -> sent
    # --------------------------------------------------------

    response = procurement_client.post(
        "/api/v1/purchase-orders/PO1001/transition",
        json={
            "actor": "harish",
            "target_state": "sent",
        },
    )

    assert response.status_code == 200

    # --------------------------------------------------------
    # Bulk send both
    #
    # PO1001 = already sent -> FAIL
    # PO1002 = draft -> SUCCESS
    # --------------------------------------------------------

    response = procurement_client.post(
        "/api/v1/purchase-orders/bulk-send",
        json={
            "po_numbers": [
                "PO1001",
                "PO1002",
            ],
            "actor": "harish",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 2
    assert body["successful"] == 1
    assert body["failed"] == 1

    results = body["results"]

    # --------------------------------------------------------
    # PO1001
    # --------------------------------------------------------

    assert results[0]["po_number"] == "PO1001"
    assert results[0]["success"] is False
    assert results[0]["status"] == "sent"
    assert results[0]["error"] is not None

    # --------------------------------------------------------
    # PO1002
    # --------------------------------------------------------

    assert results[1]["po_number"] == "PO1002"
    assert results[1]["success"] is True
    assert results[1]["status"] == "sent"
    assert results[1]["error"] is None

# ============================================================
# R5 AUTHORIZATION / SUPPLIER SCOPING TESTS
# ============================================================

def test_supplier_can_access_own_purchase_order(
    procurement_client,
    supplier_client,
):
    """
    R5:
    Supplier SUP001 must be able to access its own Purchase Order.
    """

    create_sample_po(
        procurement_client,
        po_number="PO2001",
        supplier_id="SUP001",
    )

    response = supplier_client.get(
        "/api/v1/purchase-orders/PO2001"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["po_number"] == "PO2001"
    assert body["supplier_id"] == "SUP001"


def test_supplier_cannot_access_other_supplier_purchase_order(
    procurement_client,
    supplier_client,
):
    """
    R5 Supplier Scoping:

    Authenticated supplier = SUP001
    Requested PO supplier = SUP002

    The supplier must not be able to access another
    supplier's Purchase Order.
    """

    create_sample_po(
        procurement_client,
        po_number="PO2002",
        supplier_id="SUP002",
    )

    response = supplier_client.get(
        "/api/v1/purchase-orders/PO2002"
    )

    assert response.status_code == 403

    assert (
        response.json()["detail"]
        == "Forbidden: supplier does not own this Purchase Order"
    )


def test_supplier_cannot_acknowledge_other_supplier_purchase_order(
    procurement_client,
    supplier_client,
):
    """
    R5 Supplier Scoping:

    SUP001 must not be able to acknowledge a PO
    that belongs to SUP002.
    """

    create_sample_po(
        procurement_client,
        po_number="PO2003",
        supplier_id="SUP002",
    )

    # Internal procurement action:
    # draft -> sent
    response = send_po(
        procurement_client,
        po_number="PO2003",
    )

    assert response.status_code == 200

    # SUP001 attempts to acknowledge SUP002's PO.
    response = supplier_client.post(
        "/api/v1/purchase-orders/PO2003/acknowledge"
    )

    assert response.status_code == 403

    assert (
        response.json()["detail"]
        == "Forbidden: supplier does not own this Purchase Order"
    )


def test_supplier_cannot_view_other_supplier_purchase_order_events(
    procurement_client,
    supplier_client,
):
    """
    R5 Supplier Scoping:

    SUP001 must not be able to view the event/history
    of a PO owned by SUP002.
    """

    create_sample_po(
        procurement_client,
        po_number="PO2004",
        supplier_id="SUP002",
    )

    # Create an event so the PO has history.
    response = send_po(
        procurement_client,
        po_number="PO2004",
    )

    assert response.status_code == 200

    # SUP001 attempts to view SUP002's PO history.
    response = supplier_client.get(
        "/api/v1/purchase-orders/PO2004/events"
    )

    assert response.status_code == 403

    assert (
        response.json()["detail"]
        == "Forbidden: supplier does not own this Purchase Order"
    )


def test_supplier_cannot_bulk_send_purchase_orders(
    supplier_client,
):
    response = supplier_client.post(
        "/api/v1/purchase-orders/bulk-send",
        json={
            "po_numbers": [
                "PO2001",
            ],
            "actor": "supplier",
        },
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "Role 'supplier' is not authorized for this endpoint"
    )

# ============================================================
# R5 AUTHORIZATION - CREATE PURCHASE ORDER
# ============================================================


def test_supplier_cannot_create_purchase_order(
    supplier_client,
):
    """
    R5:
    Supplier must not be allowed to create a Purchase Order.

    PO creation is an internal procurement operation.
    """

    response = supplier_client.post(
        "/api/v1/purchase-orders",
        json={
            "po_number": "PO3001",
            "supplier_id": "SUP001",
            "items": [
                {
                    "item_code": "LAP001",
                    "description": "Laptop",
                    "quantity": 1,
                    "unit_price": 5000,
                }
            ],
            "total_amount": 5000,
            "created_at": "2026-07-23T10:00:00",
            "expected_delivery": "2026-07-30",
        },
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "Role 'supplier' is not authorized "
        "for this endpoint"
    )


def test_compliance_cannot_create_purchase_order(
    compliance_client,
):
    """
    R5:
    Compliance officer must not create Purchase Orders.
    """

    response = compliance_client.post(
        "/api/v1/purchase-orders",
        json={
            "po_number": "PO3002",
            "supplier_id": "SUP001",
            "items": [
                {
                    "item_code": "LAP001",
                    "description": "Laptop",
                    "quantity": 1,
                    "unit_price": 5000,
                }
            ],
            "total_amount": 5000,
            "created_at": "2026-07-23T10:00:00",
            "expected_delivery": "2026-07-30",
        },
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "Role 'compliance_officer' is not authorized "
        "for this endpoint"
    )


# ============================================================
# R5 AUTHORIZATION - PURCHASE ORDER TRANSITION
# ============================================================


def test_supplier_cannot_transition_purchase_order(
    supplier_client,
):
    """
    R5:
    Supplier must not be allowed to perform
    procurement-only PO state transitions.
    """

    purchase_orders["PO3003"] = {
        "po_number": "PO3003",
        "supplier_id": "SUP001",
        "items": [],
        "total_amount": 0,
        "status": "draft",
        "created_at": "2026-07-23T10:00:00",
        "expected_delivery": "2026-07-30",
        "actual_delivery_date": None,
        "history": [],
    }

    response = supplier_client.post(
        "/api/v1/purchase-orders/PO3003/transition",
        json={
            "actor": "supplier",
            "target_state": "sent",
        },
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "Role 'supplier' is not authorized "
        "for this endpoint"
    )


def test_compliance_cannot_transition_purchase_order(
    compliance_client,
):
    """
    R5:
    Compliance officer must not perform
    procurement-only PO transitions.
    """

    purchase_orders["PO3004"] = {
        "po_number": "PO3004",
        "supplier_id": "SUP001",
        "items": [],
        "total_amount": 0,
        "status": "draft",
        "created_at": "2026-07-23T10:00:00",
        "expected_delivery": "2026-07-30",
        "actual_delivery_date": None,
        "history": [],
    }

    response = compliance_client.post(
        "/api/v1/purchase-orders/PO3004/transition",
        json={
            "actor": "compliance",
            "target_state": "sent",
        },
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "Role 'compliance_officer' is not authorized "
        "for this endpoint"
    )


def test_transition_uses_authenticated_user_email_as_actor(
    procurement_client,
):
    """
    R5:
    The transition actor must come from the authenticated
    user's identity, not from the request body.

    This prevents clients from impersonating another actor.
    """

    purchase_orders["PO3005"] = {
        "po_number": "PO3005",
        "supplier_id": "SUP001",
        "items": [],
        "total_amount": 0,
        "status": "draft",
        "created_at": "2026-07-23T10:00:00",
        "expected_delivery": "2026-07-30",
        "actual_delivery_date": None,
        "history": [],
    }

    response = procurement_client.post(
        "/api/v1/purchase-orders/PO3005/transition",
        json={
            # This value must be ignored by the route.
            "actor": "attacker@example.com",
            "target_state": "sent",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "sent"
    assert len(body["history"]) == 1

    event = body["history"][0]

    assert event["actor"] == (
        "procurementmanager@company.com"
    )

    assert event["actor"] != "attacker@example.com"


# ============================================================
# R5 AUTHORIZATION - UPDATE PURCHASE ORDER
# ============================================================


def test_supplier_can_update_own_purchase_order(
    supplier_client,
):
    """
    R5:
    Supplier SUP001 can update its own Purchase Order.
    """

    purchase_orders["PO3006"] = {
    "po_number": "PO3006",
    "supplier_id": "SUP001",
    "items": [
        {
            "item_code": "LAP001",
            "description": "Laptop",
            "quantity": 1,
            "unit_price": 5000,
        }
    ],
    "total_amount": 5000,
    "status": "draft",
    "created_at": "2026-07-23T10:00:00",
    "expected_delivery": "2026-07-30",
    "actual_delivery_date": None,
    "history": [],
}

    response = supplier_client.put(
        "/api/v1/purchase-orders/PO3006",
        json={
            "total_amount": 5000,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["po_number"] == "PO3006"
    assert body["supplier_id"] == "SUP001"


def test_supplier_cannot_update_other_supplier_purchase_order(
    supplier_client,
):
    """
    R5 Supplier Scoping:

    Authenticated supplier = SUP001
    Requested PO supplier = SUP002

    Update must be rejected with 403.
    """

    purchase_orders["PO3007"] = {
        "po_number": "PO3007",
        "supplier_id": "SUP002",
        "items": [],
        "total_amount": 5000,
        "status": "draft",
        "created_at": "2026-07-23T10:00:00",
        "expected_delivery": "2026-07-30",
        "actual_delivery_date": None,
        "history": [],
    }

    response = supplier_client.put(
        "/api/v1/purchase-orders/PO3007",
        json={
            "total_amount": 6000,
        },
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "Forbidden: supplier does not own this Purchase Order"
    )


def test_compliance_cannot_update_purchase_order(
    compliance_client,
):
    """
    R5:
    Compliance officer cannot update Purchase Orders.
    """

    purchase_orders["PO3008"] = {
        "po_number": "PO3008",
        "supplier_id": "SUP001",
        "items": [],
        "total_amount": 5000,
        "status": "draft",
        "created_at": "2026-07-23T10:00:00",
        "expected_delivery": "2026-07-30",
        "actual_delivery_date": None,
        "history": [],
    }

    response = compliance_client.put(
        "/api/v1/purchase-orders/PO3008",
        json={
            "total_amount": 6000,
        },
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "Forbidden: insufficient permissions"
    )


def test_supplier_without_supplier_id_cannot_update_po(
    supplier_no_id_client,
):
    """
    R5:
    A supplier token without supplier_id must not
    be allowed to access supplier-scoped PO operations.
    """

    purchase_orders["PO3009"] = {
        "po_number": "PO3009",
        "supplier_id": "SUP001",
        "items": [],
        "total_amount": 5000,
        "status": "draft",
        "created_at": "2026-07-23T10:00:00",
        "expected_delivery": "2026-07-30",
        "actual_delivery_date": None,
        "history": [],
    }

    response = supplier_no_id_client.put(
        "/api/v1/purchase-orders/PO3009",
        json={
            "total_amount": 6000,
        },
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "Supplier identity is missing"
    )


# ============================================================
# R5 AUTHORIZATION - DELETE PURCHASE ORDER
# ============================================================


def test_supplier_can_delete_own_purchase_order(
    supplier_client,
):
    """
    R5:
    Supplier can delete a Purchase Order belonging
    to that supplier.
    """

    purchase_orders["PO3010"] = {
        "po_number": "PO3010",
        "supplier_id": "SUP001",
        "items": [],
        "total_amount": 5000,
        "status": "draft",
        "created_at": "2026-07-23T10:00:00",
        "expected_delivery": "2026-07-30",
        "actual_delivery_date": None,
        "history": [],
    }

    response = supplier_client.delete(
        "/api/v1/purchase-orders/PO3010"
    )

    assert response.status_code == 200

    assert "deleted successfully" in (
        response.json()["message"]
    )

    assert "PO3010" not in purchase_orders


def test_supplier_cannot_delete_other_supplier_purchase_order(
    supplier_client,
):
    """
    R5 Supplier Scoping:

    SUP001 attempts to delete a PO owned by SUP002.
    """

    purchase_orders["PO3011"] = {
        "po_number": "PO3011",
        "supplier_id": "SUP002",
        "items": [],
        "total_amount": 5000,
        "status": "draft",
        "created_at": "2026-07-23T10:00:00",
        "expected_delivery": "2026-07-30",
        "actual_delivery_date": None,
        "history": [],
    }

    response = supplier_client.delete(
        "/api/v1/purchase-orders/PO3011"
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "Forbidden: supplier does not own this Purchase Order"
    )

    assert "PO3011" in purchase_orders


def test_compliance_cannot_delete_purchase_order(
    compliance_client,
):
    """
    R5:
    Compliance officer cannot delete Purchase Orders.
    """

    purchase_orders["PO3012"] = {
        "po_number": "PO3012",
        "supplier_id": "SUP001",
        "items": [],
        "total_amount": 5000,
        "status": "draft",
        "created_at": "2026-07-23T10:00:00",
        "expected_delivery": "2026-07-30",
        "actual_delivery_date": None,
        "history": [],
    }

    response = compliance_client.delete(
        "/api/v1/purchase-orders/PO3012"
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "Forbidden: insufficient permissions"
    )


def test_supplier_without_supplier_id_cannot_delete_po(
    supplier_no_id_client,
):
    """
    R5:
    Supplier without supplier_id must not be able
    to delete a Purchase Order.
    """

    purchase_orders["PO3013"] = {
        "po_number": "PO3013",
        "supplier_id": "SUP001",
        "items": [],
        "total_amount": 5000,
        "status": "draft",
        "created_at": "2026-07-23T10:00:00",
        "expected_delivery": "2026-07-30",
        "actual_delivery_date": None,
        "history": [],
    }

    response = supplier_no_id_client.delete(
        "/api/v1/purchase-orders/PO3013"
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "Supplier identity is missing"
    )

    assert "PO3013" in purchase_orders


def test_delete_purchase_order_not_found(
    supplier_client,
):
    """
    R5:
    Deleting a non-existent PO returns 404.
    """

    response = supplier_client.delete(
        "/api/v1/purchase-orders/PO9999"
    )

    assert response.status_code == 404

    assert response.json()["detail"] == (
        "Purchase Order not found"
    )


# ============================================================
# R5 SUPPLIER LIST SCOPING
# ============================================================


def test_supplier_list_returns_only_own_purchase_orders(
    supplier_client,
):
    """
    R5 Supplier Scoping:

    Supplier SUP001 must receive only POs belonging
    to SUP001.
    """

    purchase_orders["PO3014"] = {
        "po_number": "PO3014",
        "supplier_id": "SUP001",
        "items": [],
        "total_amount": 5000,
        "status": "draft",
        "created_at": "2026-07-23T10:00:00",
        "expected_delivery": "2026-07-30",
        "actual_delivery_date": None,
        "history": [],
    }

    purchase_orders["PO3015"] = {
        "po_number": "PO3015",
        "supplier_id": "SUP002",
        "items": [],
        "total_amount": 7000,
        "status": "draft",
        "created_at": "2026-07-23T10:00:00",
        "expected_delivery": "2026-07-30",
        "actual_delivery_date": None,
        "history": [],
    }

    response = supplier_client.get(
        "/api/v1/purchase-orders"
    )

    assert response.status_code == 200

    body = response.json()

    po_numbers = [
        po["po_number"]
        for po in body
    ]

    assert "PO3014" in po_numbers
    assert "PO3015" not in po_numbers

    for po in body:
        assert po["supplier_id"] == "SUP001"


def test_supplier_without_supplier_id_cannot_list_purchase_orders(
    supplier_no_id_client,
):
    """
    R5:
    Supplier without supplier_id must not receive
    an unrestricted Purchase Order list.
    """

    purchase_orders["PO3016"] = {
        "po_number": "PO3016",
        "supplier_id": "SUP001",
        "items": [],
        "total_amount": 5000,
        "status": "draft",
        "created_at": "2026-07-23T10:00:00",
        "expected_delivery": "2026-07-30",
        "actual_delivery_date": None,
        "history": [],
    }

    response = supplier_no_id_client.get(
        "/api/v1/purchase-orders"
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "Supplier identity is missing"
    )


# ============================================================
# R5 PROCUREMENT MANAGER DELETE
# ============================================================


def test_procurement_manager_can_delete_any_supplier_po(
    procurement_client,
):
    """
    R5:
    Procurement manager is an internal role and can
    delete a PO belonging to any supplier.
    """

    purchase_orders["PO3017"] = {
        "po_number": "PO3017",
        "supplier_id": "SUP002",
        "items": [],
        "total_amount": 7000,
        "status": "draft",
        "created_at": "2026-07-23T10:00:00",
        "expected_delivery": "2026-07-30",
        "actual_delivery_date": None,
        "history": [],
    }

    response = procurement_client.delete(
        "/api/v1/purchase-orders/PO3017"
    )

    assert response.status_code == 200

    assert "PO3017" not in purchase_orders