from io import BytesIO

from fastapi.testclient import TestClient

from app.main import app
from app.services.purchase_order_service import purchase_orders
from app.services.invoice_service import invoices


client = TestClient(app)


def setup_function():
    """
    Clear in-memory storage before every test.
    """
    purchase_orders.clear()
    invoices.clear()


def create_sample_po():
    """
    Create a Purchase Order required for invoice tests.
    """
    return client.post(
        "/api/v1/purchase-orders",
        json={
            "po_number": "PO1001",
            "supplier_id": "SUP001",
            "items": [
                "Laptop",
                "Mouse"
            ],
            "total_amount": 50000,
            "created_at": "2026-07-23T10:00:00",
            "expected_delivery": "2026-07-30"
        }
    )


def create_sample_invoice():
    """
    Create an Invoice.
    """
    return client.post(
        "/api/v1/invoices",
        json={
            "invoice_number": "INV1001",
            "po_number": "PO1001",
            "supplier_id": "SUP001",
            "amount": 50000,
            "invoice_date": "2026-07-23"
        }
    )


def test_create_invoice():

    create_sample_po()

    response = create_sample_invoice()

    assert response.status_code == 201

    body = response.json()

    assert body["invoice_number"] == "INV1001"

    assert body["document_url"] is None


def test_duplicate_invoice():

    create_sample_po()

    create_sample_invoice()

    response = create_sample_invoice()

    assert response.status_code == 400

    assert response.json()["detail"] == "Invoice already exists."


def test_invoice_po_not_found():

    response = client.post(
        "/api/v1/invoices",
        json={
            "invoice_number": "INV1001",
            "po_number": "PO9999",
            "supplier_id": "SUP001",
            "amount": 50000,
            "invoice_date": "2026-07-23"
        }
    )

    assert response.status_code == 400

    assert response.json()["detail"] == "Purchase Order not found."


def test_upload_invoice_pdf():

    create_sample_po()

    create_sample_invoice()

    pdf = BytesIO(
        b"%PDF-1.4\nThis is a sample PDF"
    )

    response = client.post(
        "/api/v1/invoices/INV1001/document",
        files={
            "file": (
                "invoice.pdf",
                pdf,
                "application/pdf"
            )
        }
    )

    assert response.status_code == 200

    body = response.json()

    assert body["document_url"] is not None

    assert body["document_url"].endswith("INV1001.pdf")


def test_invalid_file_type_rejected():

    create_sample_po()

    create_sample_invoice()

    txt = BytesIO(
        b"Hello World"
    )

    response = client.post(
        "/api/v1/invoices/INV1001/document",
        files={
            "file": (
                "sample.txt",
                txt,
                "text/plain"
            )
        }
    )

    assert response.status_code == 400

    assert response.json()["detail"] == "Only PDF files are allowed."


def test_invalid_pdf_signature():

    create_sample_po()

    create_sample_invoice()

    fake_pdf = BytesIO(
        b"Not a PDF"
    )

    response = client.post(
        "/api/v1/invoices/INV1001/document",
        files={
            "file": (
                "invoice.pdf",
                fake_pdf,
                "application/pdf"
            )
        }
    )

    assert response.status_code == 400

    assert response.json()["detail"] == "Invalid PDF file."