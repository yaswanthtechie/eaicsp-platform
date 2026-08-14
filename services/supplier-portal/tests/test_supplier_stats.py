from fastapi.testclient import TestClient

from app.main import app
from app.services.purchase_order_service import purchase_orders
from app.services.invoice_service import invoices

from datetime import date

client = TestClient(app)


def setup_function():
    purchase_orders.clear()
    invoices.clear()



def create_sample_data():
    purchase_orders["PO1001"] = {
        "po_number": "PO1001",
        "supplier_id": "SUP001",
        "status": "fulfilled",
        "created_at": "2026-07-20T10:00:00",
        "expected_delivery": date(2026, 7, 29),
        "actual_delivery_date": date(2026, 7, 28),
    }

    purchase_orders["PO1002"] = {
        "po_number": "PO1002",
        "supplier_id": "SUP001",
        "status": "acknowledged",
        "created_at": "2026-07-22T10:00:00",
        "expected_delivery": date(2026, 7, 31),
        "actual_delivery_date": None,
    }

    invoices["INV1001"] = {
        "invoice_number": "INV1001",
        "po_number": "PO1001",
        "supplier_id": "SUP001",
        "invoice_date": "2026-07-23",
    }

def test_supplier_stats():

    create_sample_data()

    response = client.get(
        "/api/v1/suppliers/SUP001/stats"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["supplier_id"] == "SUP001"

    assert body["po_count"] == 2
    assert body["on_time_percentage"] == 50.0
    assert body["average_invoice_cycle_time"] == 3.0

def test_supplier_not_found():

    response = client.get(
        "/api/v1/suppliers/SUP999/stats"
    )

    assert response.status_code == 404

    assert (
        response.json()["detail"]
        == "Supplier 'SUP999' not found."
    )