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

    Item total:
        Laptop: 10 × 5000 = 50000
        Mouse:   10 × 500  = 5000
        ----------------------------
        Total              = 55000

    PO creation is an internal procurement operation,
    therefore this helper should normally receive
    procurement_client.
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

    assert response.status_code == 201

    return response


def send_po(client, po_number="PO1001"):
    """
    draft -> sent

    Uses the authenticated procurement manager.
    """

    return client.post(
        f"/api/v1/purchase-orders/{po_number}/transition",
        json={
            "actor": "harish",
            "target_state": "sent",
        },
    )


def acknowledge_po(client, po_number="PO1001"):
    """
    sent -> acknowledged

    Uses the authenticated supplier.
    """

    return client.post(
        f"/api/v1/purchase-orders/{po_number}/acknowledge"
    )


def fulfill_po(client, po_number="PO1001"):
    """
    acknowledged -> fulfilled

    Uses the authenticated procurement manager.
    """

    return client.post(
        f"/api/v1/purchase-orders/{po_number}/transition",
        json={
            "actor": "dhanush",
            "target_state": "fulfilled",
        },
    )


def cancel_po(client, po_number="PO1001", actor="siri"):
    """
    Move PO to cancelled state.
    """

    return client.post(
        f"/api/v1/purchase-orders/{po_number}/transition",
        json={
            "actor": actor,
            "target_state": "cancelled",
        },
    )


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

    create_sample_po(procurement_client)

    response = send_po(procurement_client)

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "sent"

    assert len(body["history"]) == 1

    event = body["history"][0]

    assert event["from_status"] == "draft"
    assert event["to_status"] == "sent"
    assert event["actor"] == "harish"
    assert "timestamp" in event


def test_sent_to_acknowledged(
    procurement_client,
    supplier_client,
):

    create_sample_po(procurement_client)

    response = send_po(procurement_client)

    assert response.status_code == 200

    response = acknowledge_po(supplier_client)

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "acknowledged"

    assert len(body["history"]) == 2

    event = body["history"][1]

    assert event["from_status"] == "sent"
    assert event["to_status"] == "acknowledged"
    assert event["actor"] == "supplier"
    assert "timestamp" in event


def test_acknowledged_to_fulfilled(
    procurement_client,
    supplier_client,
):

    create_sample_po(procurement_client)

    send_response = send_po(procurement_client)

    assert send_response.status_code == 200

    acknowledge_response = acknowledge_po(
        supplier_client
    )

    assert acknowledge_response.status_code == 200

    response = fulfill_po(procurement_client)

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "fulfilled"

    assert len(body["history"]) == 3

    event = body["history"][2]

    assert event["from_status"] == "acknowledged"
    assert event["to_status"] == "fulfilled"
    assert event["actor"] == "dhanush"

    assert "timestamp" in event

    assert body["actual_delivery_date"] is not None


def test_draft_to_cancelled(procurement_client):

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
    assert event["actor"] == "siri"


def test_sent_to_cancelled(procurement_client):

    create_sample_po(procurement_client)

    response = send_po(procurement_client)

    assert response.status_code == 200

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


def test_acknowledged_to_cancelled(
    procurement_client,
    supplier_client,
):

    create_sample_po(procurement_client)

    send_response = send_po(procurement_client)

    assert send_response.status_code == 200

    acknowledge_response = acknowledge_po(
        supplier_client
    )

    assert acknowledge_response.status_code == 200

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

    assert body[0]["actor"] == "harish"
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