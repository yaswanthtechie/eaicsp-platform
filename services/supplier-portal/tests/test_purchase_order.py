from fastapi.testclient import TestClient

from app.main import app
from app.services.purchase_order_service import purchase_orders, po_events
from app.services.invoice_service import invoices


client = TestClient(app)


def setup_function():
    """
    Clear in-memory storage before every test.
    """
    purchase_orders.clear()
    invoices.clear()
    po_events.clear()

def create_sample_po():

    response = client.post(
        "/api/v1/purchase-orders",
        json={
            "po_number": "PO1001",
            "supplier_id": "SUP001",
            "items": ["Laptop", "Mouse"],
            "total_amount": 50000,
            "created_at": "2026-07-23T10:00:00",
            "expected_delivery": "2026-07-30"
        }
    )

    assert response.status_code == 201

    return response

def create_acknowledged_po():

    create_sample_po()

    response = client.post(
        "/api/v1/purchase-orders/PO1001/transition",
        json={
            "actor": "harish",
            "target_state": "sent"
        }
    )

    assert response.status_code == 200

    response = client.post(
        "/api/v1/purchase-orders/PO1001/acknowledge"
    )

    assert response.status_code == 200

    return response

def test_create_purchase_order():

    response = create_sample_po()

    assert response.status_code == 201

    body = response.json()

    assert body["po_number"] == "PO1001"
    assert body["status"] == "draft"


def test_get_all_purchase_orders():

    create_sample_po()

    response = client.get("/api/v1/purchase-orders")

    assert response.status_code == 200

    assert len(response.json()) == 1


def test_get_purchase_order_by_id():

    create_sample_po()

    response = client.get(
        "/api/v1/purchase-orders/PO1001"
    )

    assert response.status_code == 200

    assert response.json()["po_number"] == "PO1001"


def test_update_purchase_order():

    create_sample_po()

    response = client.put(
        "/api/v1/purchase-orders/PO1001",
        json={
            "total_amount": 75000
        }
    )

    assert response.status_code == 200

    assert response.json()["total_amount"] == 75000
    body = response.json()

    assert body["po_number"] == "PO1001"
    assert body["total_amount"] == 75000

def test_transition_draft_to_sent():

    create_sample_po()

    response = client.post(
        "/api/v1/purchase-orders/PO1001/transition",
        json={
             "actor": "harish",
             "target_state": "sent"
        }
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "sent"

    assert len(body["history"]) == 1

    assert body["history"][0]["from_status"] == "draft"

    assert body["history"][0]["to_status"] == "sent"

    assert "timestamp" in body["history"][0]
    assert body["history"][0]["actor"] == "harish"

def test_acknowledge_purchase_order():

    create_sample_po()

    client.post(
        "/api/v1/purchase-orders/PO1001/transition",
        json={
            "actor": "harish",
            "target_state": "sent"
        }
    )

    response = client.post(
        "/api/v1/purchase-orders/PO1001/acknowledge"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "acknowledged"

    assert len(body["history"]) == 2

    assert body["history"][1]["from_status"] == "sent"

    assert body["history"][1]["to_status"] == "acknowledged"

    assert "timestamp" in body["history"][1]
    assert body["history"][1]["actor"] == "supplier"

   


def test_illegal_transition():

    create_sample_po()

    response = client.post(
        "/api/v1/purchase-orders/PO1001/transition",
        json={
           "actor": "harish",
            "target_state": "sent"
        }
    )
    assert response.status_code == 200

    response = client.post(
        "/api/v1/purchase-orders/PO1001/transition",
        json={
             "actor": "dhanush",
             "target_state": "fulfilled"
        }
    )

    assert response.status_code == 400

    assert (
    "Cannot go from sent to fulfilled"
    in response.json()["detail"]
     )


def test_delete_purchase_order():

    create_sample_po()

    response = client.delete(
        "/api/v1/purchase-orders/PO1001"
    )

    assert response.status_code == 200

    response = client.get(
        "/api/v1/purchase-orders/PO1001"
    )

    assert response.status_code == 404

def test_actor_history():

    create_sample_po()

    response = client.post(
        "/api/v1/purchase-orders/PO1001/transition",
        json={
            "actor": "harish",
            "target_state": "sent"
        }
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body["history"]) == 1

    assert body["history"][0]["actor"] == "harish"
   
def test_fulfilled_transition():

    create_sample_po()

    response = client.post(
        "/api/v1/purchase-orders/PO1001/transition",
        json={
            "actor": "harish",
            "target_state": "sent"
        }
    )

    assert response.status_code == 200

    response = client.post(
        "/api/v1/purchase-orders/PO1001/acknowledge"
    )

    assert response.status_code == 200

    response = client.post(
        "/api/v1/purchase-orders/PO1001/transition",
        json={
            "actor": "dhanush",
            "target_state": "fulfilled"
        }
    )

    body = response.json()

    assert response.status_code == 200

    assert body["status"] == "fulfilled"

    assert len(body["history"]) == 3

    assert body["history"][2]["actor"] == "dhanush"

    assert body["history"][2]["from_status"] == "acknowledged"

    assert body["history"][2]["to_status"] == "fulfilled"

    assert body["actual_delivery_date"] is not None

def test_cancel_transition():

    create_sample_po()

    response = client.post(
        "/api/v1/purchase-orders/PO1001/transition",
        json={
            "actor": "siri",
            "target_state": "cancelled"
        }
    )

    body = response.json()

    assert response.status_code == 200

    assert body["status"] == "cancelled"

    assert len(body["history"]) == 1

    assert body["history"][0]["actor"] == "siri"

    assert body["history"][0]["from_status"] == "draft"

    assert body["history"][0]["to_status"] == "cancelled"

    assert "timestamp" in body["history"][0]


def test_duplicate_invoice():

    create_sample_po()

    client.post(
        "/api/v1/purchase-orders/PO1001/transition",
        json={
            "actor": "harish",
            "target_state": "sent"
        }
    )

    client.post(
        "/api/v1/purchase-orders/PO1001/acknowledge"
    )

    response = client.post(
        "/api/v1/invoices",
        json={
            "invoice_number": "INV001",
            "po_number": "PO1001",
            "supplier_id": "SUP001",
            "amount": 50000,
            "invoice_date": "2026-07-30"
        }
    )

    assert response.status_code == 201

    response = client.post(
        "/api/v1/invoices",
        json={
            "invoice_number": "INV001",
            "po_number": "PO1001",
            "supplier_id": "SUP001",
            "amount": 50000,
            "invoice_date": "2026-07-30"
        }
    )

    body = response.json()

    assert response.status_code == 400

    assert "already exists" in body["detail"]

def test_get_purchase_order_events():

    create_acknowledged_po()

    response = client.get(
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


def test_invoice_amount_tolerance():

    create_sample_po()

    client.post(
        "/api/v1/purchase-orders/PO1001/transition",
        json={
            "actor": "harish",
            "target_state": "sent"
        }
    )

    client.post(
        "/api/v1/purchase-orders/PO1001/acknowledge"
    )

    response = client.post(
        "/api/v1/invoices",
        json={
            "invoice_number": "INV001",
            "po_number": "PO1001",
            "supplier_id": "SUP001",
            "amount": 80000,
            "invoice_date": "2026-07-30"
        }
    )

    body = response.json()

    assert response.status_code == 400

    assert "Invoice amount must be between" in body["detail"]

def test_supplier_stats():

    create_sample_po()

    client.post(
        "/api/v1/purchase-orders/PO1001/transition",
        json={
            "actor": "harish",
            "target_state": "sent"
        }
    )

    client.post(
        "/api/v1/purchase-orders/PO1001/acknowledge"
    )

    client.post(
        "/api/v1/purchase-orders/PO1001/transition",
        json={
            "actor": "dhanush",
            "target_state": "fulfilled"
        }
    )

    client.post(
        "/api/v1/invoices",
        json={
            "invoice_number": "INV001",
            "po_number": "PO1001",
            "supplier_id": "SUP001",
            "amount": 50000,
            "invoice_date": "2026-07-30"
        }
    )

    response = client.get(
        "/api/v1/suppliers/SUP001/stats"
    )

    body = response.json()

    assert response.status_code == 200

    assert body["supplier_id"] == "SUP001"

    assert body["po_count"] == 1

    assert "on_time_percentage" in body

    assert "average_invoice_cycle_time" in body


def test_supplier_not_found():

    response = client.get(
        "/api/v1/suppliers/SUP999/stats"
    )

    body = response.json()

    assert response.status_code == 404

    assert "not found" in body["detail"]

def test_invalid_pdf_upload():

    create_sample_po()

    client.post(
        "/api/v1/purchase-orders/PO1001/transition",
        json={
            "actor": "harish",
            "target_state": "sent"
        }
    )

    client.post(
        "/api/v1/purchase-orders/PO1001/acknowledge"
    )

    client.post(
        "/api/v1/invoices",
        json={
            "invoice_number": "INV001",
            "po_number": "PO1001",
            "supplier_id": "SUP001",
            "amount": 50000,
            "invoice_date": "2026-07-30"
        }
    )

    files = {
        "file": (
            "test.pdf",
            b"HELLO",
            "application/pdf"
        )
    }

    response = client.post(
        "/api/v1/invoices/INV001/document",
        files=files
    )

    body = response.json()

    assert response.status_code == 400
    assert body["detail"] == "Invalid PDF signature."

def test_purchase_order_events_not_found():

    response = client.get(
        "/api/v1/purchase-orders/PO9999/events"
    )

    assert response.status_code == 404

    assert (
        response.json()["detail"]
        == "Purchase Order not found"
    )

def test_purchase_order_events_empty():

    client.post(
        "/api/v1/purchase-orders",
        json={
            "po_number": "PO2001",
            "supplier_id": "SUP001",
            "items": ["Laptop"],
            "total_amount": 50000,
            "created_at": "2026-07-23T10:00:00",
            "expected_delivery": "2026-07-30"
        }
    )

    response = client.get(
        "/api/v1/purchase-orders/PO2001/events"
    )

    assert response.status_code == 200

    assert response.json() == []