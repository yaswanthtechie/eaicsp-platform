from io import BytesIO
import os
import shutil

from fastapi.testclient import TestClient

from app.main import app
from app.services.purchase_order_service import purchase_orders
from app.services.invoice_service import invoices

client = TestClient(app)


def setup_function():
    purchase_orders.clear()
    invoices.clear()

    try:
        if os.path.exists("uploads"):
            shutil.rmtree("uploads")
    except PermissionError:
        pass

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

    response = client.post(
        "/api/v1/purchase-orders/PO1001/transition",
        json={
            "actor": "harish",
            "target_state": "sent"
        }
    )
    print(response.status_code)
    

    print(response.json())

    assert response.status_code == 200

    response = client.post(
        "/api/v1/purchase-orders/PO1001/acknowledge"
    )

    print(response.json())

    assert response.status_code == 200

    return response

def create_sample_invoice():

    response = client.post(
        "/api/v1/invoices",
        json={
            "invoice_number": "INV1001",
            "po_number": "PO1001",
            "supplier_id": "SUP001",
            "amount": 50000,
            "invoice_date": "2026-07-23"
        }
    )

    return response

def test_get_all_invoices():

    create_sample_po()

    invoice1 = {
        "invoice_number": "INV1001",
        "po_number": "PO1001",
        "supplier_id": "SUP001",
        "amount": 50000,
        "invoice_date": "2026-08-06"
    }

    response1 = client.post(
        "/api/v1/invoices",
        json=invoice1
    )

    assert response1.status_code == 201


    invoice2 = {
        "invoice_number": "INV1002",
        "po_number": "PO1001",
        "supplier_id": "SUP001",
        "amount": 50000,
        "invoice_date": "2026-08-06"
    }

    response2 = client.post(
        "/api/v1/invoices",
        json=invoice2
    )

    assert response2.status_code == 201


    response = client.get(
        "/api/v1/invoices"
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2

    assert data[0]["invoice_number"] == "INV1001"
    assert data[1]["invoice_number"] == "INV1002"

def test_get_invoice_by_number():

    create_sample_po()

    invoice = {
        "invoice_number": "INV2001",
        "po_number": "PO1001",
        "supplier_id": "SUP001",
        "amount": 50000,
        "invoice_date": "2026-08-06"
    }


    create_response = client.post(
        "/api/v1/invoices",
        json=invoice
    )

    assert create_response.status_code == 201


    response = client.get(
        "/api/v1/invoices/INV2001"
    )


    assert response.status_code == 200


    data = response.json()


    assert data["invoice_number"] == "INV2001"
    assert data["po_number"] == "PO1001"
    assert data["supplier_id"] == "SUP001"
    assert data["amount"] == 50000

def test_get_invoice_not_found():

    response = client.get(
        "/api/v1/invoices/INVALID001"
    )


    assert response.status_code == 404


    assert response.json()["detail"] == "Invoice not found."

def test_duplicate_invoice():

    create_sample_po()

    response = create_sample_invoice()

    assert response.status_code == 201

    response = create_sample_invoice()

    assert response.status_code == 400

    assert "already exists" in response.json()["detail"]
    

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


def test_invalid_po_status():

    client.post(
        "/api/v1/purchase-orders",
        json={
            "po_number": "PO1002",
            "supplier_id": "SUP001",
            "items": ["Laptop"],
            "total_amount": 50000,
            "created_at": "2026-07-23T10:00:00",
            "expected_delivery": "2026-07-30"
        }
    )

    response = client.post(
        "/api/v1/invoices",
        json={
            "invoice_number": "INV2001",
            "po_number": "PO1002",
            "supplier_id": "SUP001",
            "amount": 50000,
            "invoice_date": "2026-07-23"
        }
    )

    assert response.status_code == 400

    assert "status" in response.json()["detail"]


def test_invoice_amount_too_high():

    create_sample_po() 

    response = client.post(
        "/api/v1/invoices",
        json={
            "invoice_number": "INV3001",
            "po_number": "PO1001",
            "supplier_id": "SUP001",
            "amount": 70000,
            "invoice_date": "2026-07-23"
        }
    )

    assert response.status_code == 400

    assert "Invoice amount" in response.json()["detail"]


def test_invoice_amount_too_low():

    create_sample_po()

    response = client.post(
        "/api/v1/invoices",
        json={
            "invoice_number": "INV3002",
            "po_number": "PO1001",
            "supplier_id": "SUP001",
            "amount": 30000,
            "invoice_date": "2026-07-23"
        }
    )

    assert response.status_code == 400

    assert "Invoice amount" in response.json()["detail"]

def test_duplicate_invoice_per_supplier():

    create_sample_po()

    create_sample_invoice()

    response = client.post(
        "/api/v1/invoices",
        json={
            "invoice_number": "INV1001",
            "po_number": "PO1001",
            "supplier_id": "SUP001",
            "amount": 50000,
            "invoice_date": "2026-07-23"
        }
    )

    assert response.status_code == 400

    assert "already exists" in response.json()["detail"]


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

    assert "SUP001" in body["document_url"]
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

    assert response.json()["detail"] == "Invalid PDF signature."

def test_invalid_invoice_number():

    create_sample_po()

    response = client.post(
        "/api/v1/invoices",
        json={
            "invoice_number": "INV@1001",
            "po_number": "PO1001",
            "supplier_id": "SUP001",
            "amount": 50000,
            "invoice_date": "2026-07-23"
        }
    )

    assert response.status_code == 422

def test_invoice_not_found():

    response = client.get(
        "/api/v1/invoices/INV9999/document"
    )

    assert response.status_code == 404

    assert (
        response.json()["detail"]
        == "Invoice not found."
    )

def test_document_not_found():

    create_sample_po() 

    create_sample_invoice()

    response = client.get(
        "/api/v1/invoices/INV1001/document"
    )

    assert response.status_code == 404

    assert (
        response.json()["detail"]
        == "Document not found."
    )

def test_large_pdf_rejected():

    create_sample_po()

    create_sample_invoice()

    large_pdf = BytesIO(
        b"%PDF-" + b"a" * (11 * 1024 * 1024)
    )

    response = client.post(
        "/api/v1/invoices/INV1001/document",
        files={
            "file": (
                "large.pdf",
                large_pdf,
                "application/pdf"
            )
        }
    )

    assert response.status_code == 400

    assert (
        response.json()["detail"]
        == "Maximum file size is 10 MB."
    )

def test_download_invoice_document():

    create_sample_po()

    create_sample_invoice()

    pdf = BytesIO(
        b"%PDF-1.4\nSample PDF"
    )

    client.post(
        "/api/v1/invoices/INV1001/document",
        files={
            "file": (
                "invoice.pdf",
                pdf,
                "application/pdf"
            )
        }
    )

    response = client.get(
        "/api/v1/invoices/INV1001/document"
    )

    assert response.status_code == 200

    assert response.headers[
        "content-type"
    ].startswith("application/pdf")

def test_supplier_id_cannot_escape_upload_dir():

    response = client.post(
        "/api/v1/invoices",
        json={
            "invoice_number": "INV9999",
            "po_number": "PO1001",
            "supplier_id": "../uploads_evil",
            "amount": 1000,
            "invoice_date": "2026-08-06",
        },
    )

    assert response.status_code == 422