from io import BytesIO
import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.invoice import InvoiceStatus
from app.services.purchase_order_service import purchase_orders
from app.services.invoice_service import invoices, invoice_events
from app.services.purchase_order_service import po_events


from app.services import invoice_service


client = TestClient(app)


# ============================================================
# TEST SETUP
# ============================================================

@pytest.fixture(autouse=True)
def reset_data():
    """
    Reset all in-memory data before every test.
    Also remove uploaded invoice documents.
    """

    purchase_orders.clear()
    invoices.clear()
    po_events.clear()
    invoice_events.clear()

    if os.path.exists("uploads"):
        try:
            shutil.rmtree("uploads")
        except PermissionError:
            pass

    yield

    if os.path.exists("uploads"):
        try:
            shutil.rmtree("uploads")
        except PermissionError:
            pass


# ============================================================
# TEST DATA HELPERS
# ============================================================

def create_sample_po(
    po_number="PO1001",
    supplier_id="SUP001",
    item_code="LAPTOP",
    quantity=1,
    unit_price=50000,
):
    """
    Create a Purchase Order.

    Newly created POs start in draft state.
    """

    response = client.post(
        "/api/v1/purchase-orders",
        json={
            "po_number": po_number,
            "supplier_id": supplier_id,
            "items": [
                {
                    "item_code": item_code,
                    "description": "Laptop",
                    "quantity": quantity,
                    "unit_price": unit_price,
                }
            ],
            "total_amount": quantity * unit_price,
            "created_at": "2026-08-06T10:00:00",
            "expected_delivery": "2026-08-30",
        },
    )

    assert response.status_code == 201, response.text

    return response


def acknowledge_po(po_number="PO1001"):
    """
    Move PO:

        draft -> sent -> acknowledged
    """

    response = client.post(
        f"/api/v1/purchase-orders/{po_number}/transition",
        json={
            "actor": "buyer",
            "target_state": "sent",
        },
    )

    assert response.status_code == 200, response.text

    response = client.post(
        f"/api/v1/purchase-orders/{po_number}/acknowledge"
    )

    assert response.status_code == 200, response.text

    return response


def create_acknowledged_po(
    po_number="PO1001",
    supplier_id="SUP001",
    item_code="LAPTOP",
    quantity=1,
    unit_price=50000,
):
    """
    Create a PO and move it to acknowledged state.
    """

    create_sample_po(
        po_number=po_number,
        supplier_id=supplier_id,
        item_code=item_code,
        quantity=quantity,
        unit_price=unit_price,
    )

    acknowledge_po(po_number)

    return purchase_orders[po_number]


def create_fulfilled_po(
    po_number="PO1001",
    supplier_id="SUP001",
    item_code="LAPTOP",
    quantity=1,
    unit_price=50000,
):
    """
    Create PO and move it:

        draft -> sent -> acknowledged -> fulfilled
    """

    create_acknowledged_po(
        po_number=po_number,
        supplier_id=supplier_id,
        item_code=item_code,
        quantity=quantity,
        unit_price=unit_price,
    )

    response = client.post(
        f"/api/v1/purchase-orders/{po_number}/transition",
        json={
            "actor": "buyer",
            "target_state": "fulfilled",
        },
    )

    assert response.status_code == 200, response.text

    return purchase_orders[po_number]


def invoice_payload(
    invoice_number="INV1001",
    po_number="PO1001",
    supplier_id="SUP001",
    item_code="LAPTOP",
    quantity=1,
    unit_price=50000,
    amount=None,
    invoice_date="2026-08-06",
):
    """
    Build a valid invoice payload.
    """

    if amount is None:
        amount = quantity * unit_price

    return {
        "invoice_number": invoice_number,
        "supplier_id": supplier_id,
        "items": [
            {
                "po_number": po_number,
                "item_code": item_code,
                "description": "Laptop",
                "quantity": quantity,
                "unit_price": unit_price,
            }
        ],
        "amount": amount,
        "invoice_date": invoice_date,
    }


def create_sample_invoice(
    invoice_number="INV1001",
    po_number="PO1001",
    supplier_id="SUP001",
    item_code="LAPTOP",
    quantity=1,
    unit_price=50000,
    amount=None,
):
    """
    Create an invoice.
    """

    return client.post(
        "/api/v1/invoices",
        json=invoice_payload(
            invoice_number=invoice_number,
            po_number=po_number,
            supplier_id=supplier_id,
            item_code=item_code,
            quantity=quantity,
            unit_price=unit_price,
            amount=amount,
        ),
    )

def create_submitted_invoice(
    invoice_number="INV1001",
):
    """
    Create a valid invoice.
    Newly created invoices start as submitted.
    """

    create_acknowledged_po()

    response = create_sample_invoice(
        invoice_number=invoice_number,
    )

    assert response.status_code == 201, response.text

    return response


def transition_invoice(
    invoice_number="INV1001",
    target_state="approved",
    reason=None,
    supplier_id="SUP001",
    actor_id="USER001",
    actor_name="Test User",
    role="buyer",
):
    return client.post(
        f"/api/v1/invoices/{supplier_id}/{invoice_number}/transition",
        json={
            "target_state": target_state,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "role": role,
            "reason": reason,
        },
    )
# ============================================================
# INVOICE STATE MACHINE - LEGAL TRANSITIONS
# ============================================================


def transition_invoice(
    invoice_number="INV1001",
    target_state="approved",
    reason=None,
    supplier_id="SUP001",
    actor_id="USER001",
    actor_name="Test User",
    role="buyer",
):
    return client.post(
        f"/api/v1/invoices/{supplier_id}/{invoice_number}/transition",
        json={
            "target_state": target_state,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "role": role,
            "reason": reason,
        },
    )


def adjust_invoice_api(
    invoice_number="INV1001",
    quantity=1,
    unit_price=50000,
    reason="Correcting invoice quantity.",
    supplier_id="SUP001",
):
    return client.post(
        f"/api/v1/invoices/{supplier_id}/{invoice_number}/adjust",
        json={
            "actor_id": "USER002",
            "actor_name": "Adjustment User",
            "role": "finance",
            "reason": reason,
            "items": [
                {
                    "po_number": "PO1001",
                    "item_code": "LAPTOP",
                    "description": "Laptop",
                    "quantity": quantity,
                    "unit_price": unit_price,
                }
            ],
        },
    )


def test_submitted_to_approved():
    create_submitted_invoice()

    response = transition_invoice(
        "INV1001",
        "approved",
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["status"] == "approved"


def test_submitted_to_disputed():
    create_submitted_invoice()

    response = transition_invoice(
        "INV1001",
        "disputed",
        reason="Invoice quantity does not match received goods.",
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["status"] == "disputed"

    assert data["dispute"] is not None

    assert (
        data["dispute"]["reason"]
        == "Invoice quantity does not match received goods."
    )

    assert data["dispute"]["actor_id"] == "USER001"
    assert data["dispute"]["actor_name"] == "Test User"
    assert data["dispute"]["role"] == "buyer"

    assert data["dispute"]["timestamp"] is not None


def test_submitted_to_rejected():
    create_submitted_invoice()

    response = transition_invoice(
        "INV1001",
        "rejected",
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["status"] == "rejected"

def test_adjusted_to_rejected():
    create_submitted_invoice()

    # submitted -> disputed
    response = transition_invoice(
        "INV1001",
        "disputed",
        reason="Invoice has an incorrect amount.",
    )

    assert response.status_code == 200

    # disputed -> adjusted
    response = adjust_invoice_api(
        invoice_number="INV1001",
        quantity=1,
        unit_price=50000,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "adjusted"

    # adjusted -> rejected
    response = transition_invoice(
        "INV1001",
        "rejected",
        reason="The adjustment is still incorrect.",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_disputed_to_approved():
    create_submitted_invoice()

    response = transition_invoice(
        "INV1001",
        "disputed",
        reason="Incorrect amount.",
    )

    assert response.status_code == 200

    response = transition_invoice(
        "INV1001",
        "approved",
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["status"] == "approved"

    assert data["dispute"]["resolution"] == "approved"
    assert data["dispute"]["resolved_by"] == "USER001"
    assert data["dispute"]["resolved_at"] is not None


def test_disputed_to_rejected():
    create_submitted_invoice()

    response = transition_invoice(
        "INV1001",
        "disputed",
        reason="Incorrect invoice.",
    )

    assert response.status_code == 200

    response = transition_invoice(
        "INV1001",
        "rejected",
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["status"] == "rejected"

    assert data["dispute"]["resolution"] == "rejected"
    assert data["dispute"]["resolved_by"] == "USER001"
    assert data["dispute"]["resolved_at"] is not None


def test_disputed_to_adjusted_to_approved():
    create_submitted_invoice()

    response = transition_invoice(
        "INV1001",
        "disputed",
        reason="Incorrect quantity.",
    )

    assert response.status_code == 200, response.text

    response = adjust_invoice_api(
        quantity=1,
        unit_price=50000,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["status"] == "adjusted"

    response = transition_invoice(
        "INV1001",
        "approved",
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["status"] == "approved"


def test_dispute_requires_reason():
    create_submitted_invoice()

    response = transition_invoice(
        "INV1001",
        "disputed",
    )

    assert response.status_code == 400

    detail = response.json()["detail"]

    assert "reason is required" in detail.lower()

    # IMPORTANT:
    # invoices now uses (supplier_id, invoice_number)
    invoice_key = ("SUP001", "INV1001")

    assert (
        invoices[invoice_key]["status"]
        == InvoiceStatus.submitted
    )


def test_dispute_rejects_blank_reason():
    create_submitted_invoice()

    response = transition_invoice(
        "INV1001",
        "disputed",
        reason="   ",
    )

    assert response.status_code == 400

    assert "reason is required" in (
        response.json()["detail"].lower()
    )

    invoice_key = ("SUP001", "INV1001")

    assert (
        invoices[invoice_key]["status"]
        == InvoiceStatus.submitted
    )


# ============================================================
# INVOICE STATE MACHINE - ILLEGAL TRANSITIONS
# ============================================================

@pytest.mark.parametrize(
    "current_state,target_state",
    [
        # submitted
        ("submitted", "submitted"),
        ("submitted", "adjusted"),

        # disputed
        ("disputed", "submitted"),
        ("disputed", "disputed"),

        # approved
        ("approved", "submitted"),
        ("approved", "disputed"),
        ("approved", "rejected"),
        ("approved", "adjusted"),

        # rejected
        ("rejected", "submitted"),
        ("rejected", "disputed"),
        ("rejected", "approved"),
        ("rejected", "adjusted"),

        # adjusted
        ("adjusted", "submitted"),
        ("adjusted", "disputed"),
        ("adjusted", "adjusted"),
    ],
)
def test_illegal_invoice_transitions(
    current_state,
    target_state,
):
    create_submitted_invoice()

    # --------------------------------------------------------
    # Move invoice to required current state
    # --------------------------------------------------------

    if current_state == "disputed":
        response = transition_invoice(
            "INV1001",
            "disputed",
            reason="Test dispute.",
        )

        assert response.status_code == 200, response.text

    elif current_state == "approved":
        response = transition_invoice(
            "INV1001",
            "approved",
        )

        assert response.status_code == 200, response.text

    elif current_state == "rejected":
        response = transition_invoice(
            "INV1001",
            "rejected",
        )

        assert response.status_code == 200, response.text

    elif current_state == "adjusted":
        # adjusted is reached only through the dedicated
        # adjustment endpoint.
        response = transition_invoice(
            "INV1001",
            "disputed",
            reason="Test dispute.",
        )

        assert response.status_code == 200, response.text

        response = adjust_invoice_api(
            invoice_number="INV1001",
            quantity=1,
            unit_price=50000,
        )

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "adjusted"

    # --------------------------------------------------------
    # Attempt illegal transition
    # --------------------------------------------------------

    response = transition_invoice(
        "INV1001",
        target_state,
        reason=(
            "Test reason."
            if target_state == "disputed"
            else None
        ),
    )

    assert response.status_code == 400, response.text

    detail = response.json()["detail"]

    assert "cannot go from" in detail.lower()

def test_invoice_transition_not_found():
    response = transition_invoice(
        "INV9999",
        "approved",
    )

    assert response.status_code == 404

    assert response.json()["detail"] == (
        "Invoice not found."
    )

def test_rejected_invoice_quantity_is_not_counted():
    create_acknowledged_po(
        quantity=10,
        unit_price=50000,
    )

    # First invoice consumes all 10 units
    response = create_sample_invoice(
        invoice_number="INV1001",
        quantity=10,
        amount=500000,
    )

    assert response.status_code == 201

    # Reject the invoice
    response = transition_invoice(
        invoice_number="INV1001",
        target_state="rejected",
        reason="Invoice is incorrect.",
    )

    assert response.status_code == 200

    # Because rejected invoice should no longer count,
    # another invoice for the same 10 units is allowed.
    response = create_sample_invoice(
        invoice_number="INV1002",
        quantity=10,
        amount=500000,
    )

    assert response.status_code == 201, response.text
    
def test_invoice_unit_price_exactly_5_percent_below():
    create_acknowledged_po(
        unit_price=50000,
    )

    response = create_sample_invoice(
        invoice_number="INV9101",
        unit_price=47500,
        amount=47500,
    )

    assert response.status_code == 201, response.text

def test_invoice_unit_price_exactly_5_percent_above():
    create_acknowledged_po(
        unit_price=50000,
    )

    response = create_sample_invoice(
        invoice_number="INV9102",
        unit_price=52500,
        amount=52500,
    )

    assert response.status_code == 201, response.text

def test_invoice_unit_price_just_below_5_percent_boundary():
    create_acknowledged_po(
        unit_price=50000,
    )

    response = create_sample_invoice(
        invoice_number="INV9103",
        unit_price=47499.99,
        amount=47499.99,
    )

    assert response.status_code == 400

    assert "unit price" in (
        response.json()["detail"].lower()
    )

def test_invoice_unit_price_just_above_5_percent_boundary():
    create_acknowledged_po(
        unit_price=50000,
    )

    response = create_sample_invoice(
        invoice_number="INV9104",
        unit_price=52500.01,
        amount=52500.01,
    )

    assert response.status_code == 400

    assert "unit price" in (
        response.json()["detail"].lower()
    )

def test_invoice_history_is_created_on_transition():
    create_submitted_invoice()

    response = transition_invoice(
        "INV1001",
        "approved",
        actor_id="USER001",
        actor_name="Test User",
        role="buyer",
        reason="Invoice verified.",
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert "history" in data
    assert len(data["history"]) == 1

    event = data["history"][0]

    assert event["from_status"] == "submitted"
    assert event["to_status"] == "approved"
    assert event["actor_id"] == "USER001"
    assert event["actor_name"] == "Test User"
    assert event["role"] == "buyer"
    assert event["reason"] == "Invoice verified."
    assert event["timestamp"] is not None

    invoice_key = ("SUP001", "INV1001")

    assert invoice_events[invoice_key] == data["history"]


def test_invoice_history_tracks_multiple_transitions():
    create_submitted_invoice()

    response = transition_invoice(
        "INV1001",
        "disputed",
        actor_id="USER001",
        actor_name="Test User",
        role="buyer",
        reason="Incorrect quantity.",
    )

    assert response.status_code == 200, response.text

    response = transition_invoice(
        "INV1001",
        "approved",
        actor_id="USER002",
        actor_name="Manager",
        role="manager",
        reason="Dispute resolved.",
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["status"] == "approved"
    assert len(data["history"]) == 2

    first_event = data["history"][0]
    second_event = data["history"][1]

    assert first_event["from_status"] == "submitted"
    assert first_event["to_status"] == "disputed"
    assert first_event["actor_id"] == "USER001"
    assert first_event["reason"] == "Incorrect quantity."

    assert second_event["from_status"] == "disputed"
    assert second_event["to_status"] == "approved"
    assert second_event["actor_id"] == "USER002"
    assert second_event["actor_name"] == "Manager"
    assert second_event["role"] == "manager"
    assert second_event["reason"] == "Dispute resolved."

    assert first_event["timestamp"] is not None
    assert second_event["timestamp"] is not None

    invoice_key = ("SUP001", "INV1001")

    assert invoice_events[invoice_key] == data["history"]

    

def test_valid_pdf_with_renamed_extension_is_accepted():
    create_acknowledged_po()

    response = create_sample_invoice(
        invoice_number="INV9201",
    )

    assert response.status_code == 201

    response = client.post(
        "/api/v1/invoices/SUP001/INV9201/document",
        files={
            "file": (
                "invoice.txt",
                valid_pdf(),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["invoice_number"] == "INV9201"
    assert data["document_url"] is not None

    assert data["document_url"].endswith(
        "INV9201.pdf"
    )

    assert os.path.exists(
        data["document_url"]
    )

@pytest.mark.parametrize(
    "content",
    [
        b"Not a PDF",
        b"PDF-1.4",
        b"%PNG-",
        b"%PDX-",
        b"",
    ],
)
def test_corrupted_pdf_header_rejected(content):
    create_acknowledged_po()

    response = create_sample_invoice(
        invoice_number="INV9301",
    )

    assert response.status_code == 201

    response = client.post(
        "/api/v1/invoices/SUP001/INV9301/document",
        files={
            "file": (
                "invoice.pdf",
                BytesIO(content),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "Invalid PDF signature."
    )

def test_valid_pdf_with_wrong_content_type_rejected():
    create_acknowledged_po()

    response = create_sample_invoice(
        invoice_number="INV9401",
    )

    assert response.status_code == 201

    response = client.post(
        "/api/v1/invoices/SUP001/INV9401/document",
        files={
            "file": (
                "invoice.pdf",
                valid_pdf(),
                "text/plain",
            )
        },
    )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "Only PDF files are allowed."
    )

def valid_pdf():
    return BytesIO(
        b"%PDF-1.4\n"
        b"1 0 obj\n"
        b"<< /Type /Catalog >>\n"
        b"endobj\n"
        b"%%EOF"
    )


# ============================================================
# GET ALL INVOICES
# ============================================================

def test_get_all_invoices_empty():

    response = client.get(
        "/api/v1/invoices"
    )

    assert response.status_code == 200
    assert response.json() == []


def test_get_all_invoices():

    create_acknowledged_po(
        quantity=2
    )

    response1 = create_sample_invoice(
        invoice_number="INV1001",
        quantity=1,
        amount=50000,
    )

    assert response1.status_code == 201, response1.text

    response2 = create_sample_invoice(
        invoice_number="INV1002",
        quantity=1,
        amount=50000,
    )

    assert response2.status_code == 201, response2.text

    response = client.get(
        "/api/v1/invoices"
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert data[0]["invoice_number"] == "INV1001"
    assert data[1]["invoice_number"] == "INV1002"

# ============================================================
# CREATE INVOICE
# ============================================================

def test_create_invoice_success():

    create_acknowledged_po()

    response = create_sample_invoice(
        invoice_number="INV2001"
    )

    assert response.status_code == 201

    data = response.json()

    assert data["invoice_number"] == "INV2001"
    assert data["supplier_id"] == "SUP001"
    assert data["amount"] == 50000

    assert len(data["items"]) == 1
    assert data["items"][0]["po_number"] == "PO1001"
    assert data["items"][0]["item_code"] == "LAPTOP"


# ============================================================
# GET INVOICE BY NUMBER
# ============================================================

def test_get_invoice_by_number():

    create_acknowledged_po()

    create_response = create_sample_invoice(
        invoice_number="INV2001"
    )

    assert create_response.status_code == 201, create_response.text

    response = client.get(
        "/api/v1/invoices/SUP001/INV2001"
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["invoice_number"] == "INV2001"
    assert data["supplier_id"] == "SUP001"
    assert data["amount"] == 50000

    assert data["items"][0]["po_number"] == "PO1001"


# ============================================================
# INVOICE NOT FOUND
# ============================================================

def test_get_invoice_not_found():

    response = client.get(
        "/api/v1/invoices/SUP001/INVALID001"
    )

    assert response.status_code == 404

    assert response.json()["detail"] == (
        "Invoice not found."
    )

# ============================================================
# DUPLICATE INVOICE
# ============================================================

def test_duplicate_invoice():

    create_acknowledged_po()

    response = create_sample_invoice(
        invoice_number="INV1001"
    )

    assert response.status_code == 201

    response = create_sample_invoice(
        invoice_number="INV1001"
    )

    assert response.status_code == 409

    assert "already exists" in (
        response.json()["detail"]
    )


# ============================================================
# SAME INVOICE NUMBER FOR DIFFERENT SUPPLIER
# ============================================================

def test_same_invoice_number_different_supplier():
    create_acknowledged_po(
        po_number="PO1001",
        supplier_id="SUP001",
    )

    create_acknowledged_po(
        po_number="PO1002",
        supplier_id="SUP002",
    )

    # Supplier 1 can create INV1001
    response = create_sample_invoice(
        invoice_number="INV1001",
        po_number="PO1001",
        supplier_id="SUP001",
    )

    assert response.status_code == 201, response.text

    # Supplier 2 can also create INV1001 because
    # invoice numbers are supplier-scoped.
    response = create_sample_invoice(
        invoice_number="INV1001",
        po_number="PO1002",
        supplier_id="SUP002",
    )

    assert response.status_code == 201, response.text

def test_duplicate_invoice_number_same_supplier():
    create_acknowledged_po(
        po_number="PO1001",
        supplier_id="SUP001",
    )

    response = create_sample_invoice(
        invoice_number="INV1001",
        po_number="PO1001",
        supplier_id="SUP001",
    )

    assert response.status_code == 201, response.text

    response = create_sample_invoice(
        invoice_number="INV1001",
        po_number="PO1001",
        supplier_id="SUP001",
    )

    assert response.status_code == 409, response.text

# ============================================================
# PO NOT FOUND
# ============================================================

def test_invoice_po_not_found():

    response = create_sample_invoice(
        invoice_number="INV1001",
        po_number="PO9999",
    )

    assert response.status_code == 404

    assert response.json()["detail"] == (
        "Purchase Order 'PO9999' not found."
    )


# ============================================================
# PO IN DRAFT STATUS
# ============================================================

def test_invoice_po_in_draft_status_rejected():

    create_sample_po()

    response = create_sample_invoice(
        invoice_number="INV1001"
    )

    assert response.status_code == 400

    detail = response.json()["detail"]

    assert "status" in detail.lower()
    assert "draft" in detail.lower()


# ============================================================
# PO IN SENT STATUS
# ============================================================

def test_invoice_po_in_sent_status_rejected():

    create_sample_po()

    response = client.post(
        "/api/v1/purchase-orders/PO1001/transition",
        json={
            "actor": "buyer",
            "target_state": "sent",
        },
    )

    assert response.status_code == 200

    response = create_sample_invoice(
        invoice_number="INV1001"
    )

    assert response.status_code == 400

    assert "sent" in (
        response.json()["detail"].lower()
    )


# ============================================================
# ACKNOWLEDGED PO ACCEPTED
# ============================================================

def test_invoice_acknowledged_po_accepted():

    create_acknowledged_po()

    response = create_sample_invoice(
        invoice_number="INV1001"
    )

    assert response.status_code == 201


# ============================================================
# FULFILLED PO ACCEPTED
# ============================================================

def test_invoice_fulfilled_po_accepted():

    create_fulfilled_po()

    response = create_sample_invoice(
        invoice_number="INV1001"
    )

    assert response.status_code == 201


# ============================================================
# INVALID ITEM
# ============================================================

def test_invoice_item_not_in_po():

    create_acknowledged_po(
        item_code="LAPTOP"
    )

    response = create_sample_invoice(
        invoice_number="INV1001",
        item_code="MOUSE",
    )

    assert response.status_code == 400

    detail = response.json()["detail"]

    assert "does not exist" in detail


# ============================================================
# QUANTITY GREATER THAN PO
# ============================================================

def test_invoice_quantity_exceeds_po_quantity():

    create_acknowledged_po(
        quantity=5
    )

    response = create_sample_invoice(
        invoice_number="INV1001",
        quantity=6,
    )

    assert response.status_code == 400

    detail = response.json()["detail"]

    assert "cannot exceed" in detail


# ============================================================
# PARTIAL INVOICE
# ============================================================

def test_partial_invoice():

    create_acknowledged_po(
        quantity=10
    )

    response = create_sample_invoice(
        invoice_number="INV1001",
        quantity=4,
        unit_price=50000,
        amount=200000,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["amount"] == 200000


# ============================================================
# MULTIPLE PARTIAL INVOICES
# ============================================================

def test_multiple_partial_invoices():

    create_acknowledged_po(
        quantity=10
    )

    response1 = create_sample_invoice(
        invoice_number="INV1001",
        quantity=4,
        amount=200000,
    )

    assert response1.status_code == 201

    response2 = create_sample_invoice(
        invoice_number="INV1002",
        quantity=6,
        amount=300000,
    )

    assert response2.status_code == 201


# ============================================================
# OVER-INVOICING AFTER PARTIAL INVOICE
# ============================================================

def test_over_invoice_after_partial_invoice():

    create_acknowledged_po(
        quantity=10
    )

    response1 = create_sample_invoice(
        invoice_number="INV1001",
        quantity=7,
        amount=350000,
    )

    assert response1.status_code == 201

    response2 = create_sample_invoice(
        invoice_number="INV1002",
        quantity=4,
        amount=200000,
    )

    assert response2.status_code == 400

    assert "cannot exceed" in (
        response2.json()["detail"]
    )


# ============================================================
# UNIT PRICE ABOVE TOLERANCE
# ============================================================

def test_invoice_unit_price_above_tolerance():

    create_acknowledged_po(
        unit_price=50000
    )

    response = create_sample_invoice(
        invoice_number="INV1001",
        unit_price=53000,
        amount=53000,
    )

    assert response.status_code == 400

    assert "unit price" in (
        response.json()["detail"].lower()
    )


# ============================================================
# UNIT PRICE BELOW TOLERANCE
# ============================================================

def test_invoice_unit_price_below_tolerance():

    create_acknowledged_po(
        unit_price=50000
    )

    response = create_sample_invoice(
        invoice_number="INV1001",
        unit_price=46000,
        amount=46000,
    )

    assert response.status_code == 400

    assert "unit price" in (
        response.json()["detail"].lower()
    )


# ============================================================
# AMOUNT TOO HIGH
# ============================================================

def test_invoice_amount_too_high():

    create_acknowledged_po()

    response = create_sample_invoice(
        invoice_number="INV3001",
        amount=70000,
    )

    assert response.status_code == 400

    assert "Invoice amount" in (
        response.json()["detail"]
    )


# ============================================================
# AMOUNT TOO LOW
# ============================================================

def test_invoice_amount_too_low():

    create_acknowledged_po()

    response = create_sample_invoice(
        invoice_number="INV3002",
        amount=30000,
    )

    assert response.status_code == 400

    assert "Invoice amount" in (
        response.json()["detail"]
    )


# ============================================================
# DUPLICATE PO / ITEM LINE INSIDE SAME INVOICE
# ============================================================

def test_duplicate_invoice_line():

    create_acknowledged_po()

    payload = {
        "invoice_number": "INV5001",
        "supplier_id": "SUP001",
        "items": [
            {
                "po_number": "PO1001",
                "item_code": "LAPTOP",
                "description": "Laptop",
                "quantity": 1,
                "unit_price": 50000,
            },
            {
                "po_number": "PO1001",
                "item_code": "LAPTOP",
                "description": "Laptop",
                "quantity": 1,
                "unit_price": 50000,
            },
        ],
        "amount": 100000,
        "invoice_date": "2026-08-06",
    }

    response = client.post(
        "/api/v1/invoices",
        json=payload,
    )

    assert response.status_code == 400

    assert "Duplicate invoice line" in (
        response.json()["detail"]
    )


# ============================================================
# EMPTY ITEMS
# ============================================================

def test_invoice_empty_items():

    payload = {
        "invoice_number": "INV6001",
        "supplier_id": "SUP001",
        "items": [],
        "amount": 50000,
        "invoice_date": "2026-08-06",
    }

    response = client.post(
        "/api/v1/invoices",
        json=payload,
    )

    # Pydantic min_length=1
    assert response.status_code == 422


# ============================================================
# INVALID INVOICE NUMBER
# ============================================================

def test_invalid_invoice_number():

    create_acknowledged_po()

    response = create_sample_invoice(
        invoice_number="INV@1001"
    )

    # Pydantic catches this before service layer.
    assert response.status_code == 422


# ============================================================
# INVALID SUPPLIER ID
# ============================================================

def test_invalid_supplier_id():

    create_acknowledged_po()

    response = create_sample_invoice(
        invoice_number="INV1001",
        supplier_id="../uploads_evil",
    )

    # Pydantic catches this before upload/business logic.
    assert response.status_code == 422


# ============================================================
# INVALID PO NUMBER FORMAT
# ============================================================

def test_invalid_po_number_format():

    response = client.post(
        "/api/v1/invoices",
        json={
            "invoice_number": "INV1001",
            "supplier_id": "SUP001",
            "items": [
                {
                    "po_number": "PO@1001",
                    "item_code": "LAPTOP",
                    "description": "Laptop",
                    "quantity": 1,
                    "unit_price": 50000,
                }
            ],
            "amount": 50000,
            "invoice_date": "2026-08-06",
        },
    )

    assert response.status_code == 422


# ============================================================
# INVALID ITEM CODE FORMAT
# ============================================================

def test_invalid_item_code_format():

    response = client.post(
        "/api/v1/invoices",
        json={
            "invoice_number": "INV1001",
            "supplier_id": "SUP001",
            "items": [
                {
                    "po_number": "PO1001",
                    "item_code": "LAP@TOP",
                    "description": "Laptop",
                    "quantity": 1,
                    "unit_price": 50000,
                }
            ],
            "amount": 50000,
            "invoice_date": "2026-08-06",
        },
    )

    assert response.status_code == 422


# ============================================================
# INVALID QUANTITY - ZERO
# ============================================================

def test_invoice_quantity_zero():

    response = client.post(
        "/api/v1/invoices",
        json={
            "invoice_number": "INV1001",
            "supplier_id": "SUP001",
            "items": [
                {
                    "po_number": "PO1001",
                    "item_code": "LAPTOP",
                    "description": "Laptop",
                    "quantity": 0,
                    "unit_price": 50000,
                }
            ],
            "amount": 0,
            "invoice_date": "2026-08-06",
        },
    )

    assert response.status_code == 422


# ============================================================
# INVALID UNIT PRICE - ZERO
# ============================================================

def test_invoice_unit_price_zero():

    response = client.post(
        "/api/v1/invoices",
        json={
            "invoice_number": "INV1001",
            "supplier_id": "SUP001",
            "items": [
                {
                    "po_number": "PO1001",
                    "item_code": "LAPTOP",
                    "description": "Laptop",
                    "quantity": 1,
                    "unit_price": 0,
                }
            ],
            "amount": 0,
            "invoice_date": "2026-08-06",
        },
    )

    assert response.status_code == 422


# ============================================================
# INVALID AMOUNT - ZERO
# ============================================================

def test_invoice_amount_zero():

    response = client.post(
        "/api/v1/invoices",
        json={
            "invoice_number": "INV1001",
            "supplier_id": "SUP001",
            "items": [
                {
                    "po_number": "PO1001",
                    "item_code": "LAPTOP",
                    "description": "Laptop",
                    "quantity": 1,
                    "unit_price": 50000,
                }
            ],
            "amount": 0,
            "invoice_date": "2026-08-06",
        },
    )

    assert response.status_code == 422


# ============================================================
# INVALID DATE
# ============================================================

def test_invalid_invoice_date():

    response = client.post(
        "/api/v1/invoices",
        json={
            "invoice_number": "INV1001",
            "supplier_id": "SUP001",
            "items": [
                {
                    "po_number": "PO1001",
                    "item_code": "LAPTOP",
                    "description": "Laptop",
                    "quantity": 1,
                    "unit_price": 50000,
                }
            ],
            "amount": 50000,
            "invoice_date": "invalid-date",
        },
    )

    assert response.status_code == 422


# ============================================================
# MISSING REQUIRED FIELD
# ============================================================

def test_invoice_missing_supplier_id():

    response = client.post(
        "/api/v1/invoices",
        json={
            "invoice_number": "INV1001",
            "items": [
                {
                    "po_number": "PO1001",
                    "item_code": "LAPTOP",
                    "description": "Laptop",
                    "quantity": 1,
                    "unit_price": 50000,
                }
            ],
            "amount": 50000,
            "invoice_date": "2026-08-06",
        },
    )

    assert response.status_code == 422

def test_invoice_supplier_does_not_match_po():
    create_acknowledged_po(
        po_number="PO1001",
        supplier_id="SUP001",
    )

    response = create_sample_invoice(
        invoice_number="INV1001",
        po_number="PO1001",
        supplier_id="SUP002",
    )

    assert response.status_code == 400

    assert "supplier" in (
        response.json()["detail"].lower()
    )


# ============================================================
# UPLOAD VALID PDF
# ============================================================

def test_upload_invoice_pdf():

    create_acknowledged_po()

    response = create_sample_invoice(
        invoice_number="INV1001"
    )

    assert response.status_code == 201

    response = client.post(
        "/api/v1/invoices/SUP001/INV1001/document",
        files={
            "file": (
                "invoice.pdf",
                valid_pdf(),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["invoice_number"] == "INV1001"
    assert body["document_url"] is not None

    assert "SUP001" in body["document_url"]
    assert body["document_url"].endswith(
        "INV1001.pdf"
    )

    assert os.path.exists(
        body["document_url"]
    )


# ============================================================
# UPLOAD DOCUMENT FOR NON-EXISTING INVOICE
# ============================================================

def test_upload_document_invoice_not_found():

    response = client.post(
        "/api/v1/invoices/SUP001/INV9999/document",
        files={
            "file": (
                "invoice.pdf",
                valid_pdf(),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 404

    assert response.json()["detail"] == (
        "Invoice not found."
    )

def test_invoice_quantity_exactly_matches_po_quantity():
    create_acknowledged_po(
        quantity=10,
        unit_price=50000,
    )

    response = create_sample_invoice(
        invoice_number="INV1001",
        quantity=10,
        amount=500000,
    )

    assert response.status_code == 201

def test_invoice_rejected_after_po_fully_invoiced():
    create_acknowledged_po(quantity=10)

    response = create_sample_invoice(
        invoice_number="INV1001",
        quantity=10,
        amount=500000,
    )

    assert response.status_code == 201

    response = create_sample_invoice(
        invoice_number="INV1002",
        quantity=1,
        amount=50000,
    )

    assert response.status_code == 400
    assert "cannot exceed" in response.json()["detail"]
# ============================================================
# DOCUMENT NOT FOUND
# ============================================================

def test_document_not_found():

    create_acknowledged_po()

    response = create_sample_invoice(
        invoice_number="INV1001"
    )

    assert response.status_code == 201

    response = client.get(
        "/api/v1/invoices/SUP001/INV1001/document"
    )

    assert response.status_code == 404

    assert response.json()["detail"] == (
        "Document not found."
    )


# ============================================================
# INVOICE DOCUMENT NOT FOUND
# ============================================================

def test_invoice_document_invoice_not_found():

    response = client.get(
        "/api/v1/invoices/SUP001/INV9999/document"
    )

    assert response.status_code == 404

    assert response.json()["detail"] == (
        "Invoice not found."
    )


# ============================================================
# LARGE PDF
# ============================================================

def test_large_pdf_rejected():

    create_acknowledged_po()

    response = create_sample_invoice(
        invoice_number="INV1001"
    )

    assert response.status_code == 201

    large_pdf = BytesIO(
        b"%PDF-" +
        b"a" * (11 * 1024 * 1024)
    )

    response = client.post(
        "/api/v1/invoices/SUP001/INV1001/document",
        files={
            "file": (
                "large.pdf",
                large_pdf,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "Maximum file size is 10 MB."
    )


def test_pdf_exactly_10_mb_accepted():
    create_acknowledged_po()

    response = create_sample_invoice(
        invoice_number="INV9501"
    )

    assert response.status_code == 201

    
    pdf_content = (
        b"%PDF-1.4\n"
        + b"a" * (10 * 1024 * 1024 - len(b"%PDF-1.4\n"))

   )
    
    response = client.post(
        "/api/v1/invoices/SUP001/INV9501/document",
        files={
            "file": (
                "invoice.pdf",
                BytesIO(pdf_content),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200


# ============================================================
# DOWNLOAD INVOICE DOCUMENT
# ============================================================

def test_download_invoice_document():

    create_acknowledged_po()

    response = create_sample_invoice(
        invoice_number="INV1001"
    )

    assert response.status_code == 201

    upload_response = client.post(
        "/api/v1/invoices/SUP001/INV1001/document",
        files={
            "file": (
                "invoice.pdf",
                valid_pdf(),
                "application/pdf",
            )
        },
    )

    assert upload_response.status_code == 200

    response = client.get(
        "/api/v1/invoices/SUP001/INV1001/document"
    )

    assert response.status_code == 200

    assert response.headers[
        "content-type"
    ].startswith("application/pdf")

    assert response.content.startswith(
        b"%PDF-"
    )


# ============================================================
# FILE DOES NOT EXIST AFTER UPLOAD
# ============================================================

def test_file_deleted_after_upload():

    create_acknowledged_po()

    response = create_sample_invoice(
        invoice_number="INV1001"
    )

    assert response.status_code == 201

    upload_response = client.post(
        "/api/v1/invoices/SUP001/INV1001/document",
        files={
            "file": (
                "invoice.pdf",
                valid_pdf(),
                "application/pdf",
            )
        },
    )

    assert upload_response.status_code == 200

    filepath = upload_response.json()[
        "document_url"
    ]

    assert os.path.exists(filepath)

    os.remove(filepath)

    response = client.get(
        "/api/v1/invoices/SUP001/INV1001/document"
    )

    assert response.status_code == 404

    assert response.json()["detail"] == (
        "File does not exist."
    )


# ============================================================
# DOCUMENT URL STORED
# ============================================================

def test_document_url_saved_in_memory():

    create_acknowledged_po()

    response = create_sample_invoice(
        invoice_number="INV1001"
    )

    assert response.status_code == 201

    invoice_key = ("SUP001", "INV1001")

    assert invoices[
        invoice_key
    ]["document_url"] is None

    upload_response = client.post(
        "/api/v1/invoices/SUP001/INV1001/document",
        files={
            "file": (
                "invoice.pdf",
                valid_pdf(),
                "application/pdf",
            )
        },
    )

    assert upload_response.status_code == 200, (
        upload_response.text
    )

    assert invoices[
        invoice_key
    ]["document_url"] is not None

# ============================================================
# SUPPLIER DIRECTORY
# ============================================================

def test_invoice_document_saved_under_supplier_directory():

    create_acknowledged_po(
        supplier_id="SUP123"
    )

    response = create_sample_invoice(
        invoice_number="INV1001",
        supplier_id="SUP123",
    )

    assert response.status_code == 201

    upload_response = client.post(
        "/api/v1/invoices/SUP123/INV1001/document",
        files={
            "file": (
                "invoice.pdf",
                valid_pdf(),
                "application/pdf",
            )
        },
    )

    assert upload_response.status_code == 200

    filepath = upload_response.json()[
        "document_url"
    ]

    assert "SUP123" in filepath

    assert filepath.endswith(
        os.path.join(
            "SUP123",
            "INV1001.pdf",
        )
    )


# ============================================================
# INVOICE CREATE DOES NOT CREATE DOCUMENT
# ============================================================

def test_invoice_document_url_initially_none():

    create_acknowledged_po()

    response = create_sample_invoice(
        invoice_number="INV1001"
    )

    assert response.status_code == 201

    data = response.json()

    assert data["document_url"] is None


# ============================================================
# GET AFTER UPLOAD
# ============================================================

def test_get_invoice_after_document_upload():

    create_acknowledged_po()

    response = create_sample_invoice(
        invoice_number="INV1001"
    )

    assert response.status_code == 201

    upload_response = client.post(
        "/api/v1/invoices/SUP001/INV1001/document",
        files={
            "file": (
                "invoice.pdf",
                valid_pdf(),
                "application/pdf",
            )
        },
    )

    assert upload_response.status_code == 200

    response = client.get(
        "/api/v1/invoices/SUP001/INV1001"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["invoice_number"] == "INV1001"
    assert data["document_url"] is not None


# ============================================================
# MULTI-PO INVOICE
# ============================================================

def test_invoice_with_multiple_purchase_orders():

    create_acknowledged_po(
        po_number="PO1001",
        supplier_id="SUP001",
        item_code="LAPTOP",
        quantity=5,
        unit_price=50000,
    )

    create_acknowledged_po(
        po_number="PO1002",
        supplier_id="SUP001",
        item_code="MOUSE",
        quantity=10,
        unit_price=1500,
    )

    payload = {
        "invoice_number": "INV7001",
        "supplier_id": "SUP001",
        "items": [
            {
                "po_number": "PO1001",
                "item_code": "LAPTOP",
                "description": "Laptop",
                "quantity": 2,
                "unit_price": 50000,
            },
            {
                "po_number": "PO1002",
                "item_code": "MOUSE",
                "description": "Wireless Mouse",
                "quantity": 5,
                "unit_price": 1500,
            },
        ],
        "amount": 107500,
        "invoice_date": "2026-08-06",
    }

    response = client.post(
        "/api/v1/invoices",
        json=payload,
    )

    assert response.status_code == 201

    data = response.json()

    assert len(data["items"]) == 2
    assert data["amount"] == 107500


# ============================================================
# MULTIPLE ITEMS SAME PO
# ============================================================

def test_invoice_multiple_items_same_po():

    create_sample_po(
        po_number="PO1001",
        item_code="LAPTOP",
        quantity=5,
        unit_price=50000,
    )

    # Add second item manually because the current
    # PO API accepts multiple items in one request.
    purchase_orders["PO1001"]["items"].append(
        {
            "item_code": "MOUSE",
            "description": "Mouse",
            "quantity": 10,
            "unit_price": 1500,
        }
    )

    acknowledge_po("PO1001")

    payload = {
        "invoice_number": "INV8001",
        "supplier_id": "SUP001",
        "items": [
            {
                "po_number": "PO1001",
                "item_code": "LAPTOP",
                "description": "Laptop",
                "quantity": 1,
                "unit_price": 50000,
            },
            {
                "po_number": "PO1001",
                "item_code": "MOUSE",
                "description": "Mouse",
                "quantity": 2,
                "unit_price": 1500,
            },
        ],
        "amount": 53000,
        "invoice_date": "2026-08-06",
    }

    response = client.post(
        "/api/v1/invoices",
        json=payload,
    )

    assert response.status_code == 201

    data = response.json()

    assert len(data["items"]) == 2
    assert data["amount"] == 53000


# ============================================================
# ORPHANED INVOICE FILE TEST SETUP
# ============================================================

@pytest.fixture
def orphan_test_setup(tmp_path, monkeypatch):
    """
    Create an isolated upload directory and reset
    in-memory invoice storage.
    """

    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    # invoice_service imported UPLOAD_DIR directly,
    # therefore patch the value inside invoice_service.
    monkeypatch.setattr(
        invoice_service,
        "UPLOAD_DIR",
        str(upload_dir),
    )

    # Clear in-memory storage
    invoice_service.invoices.clear()
    invoice_service.invoice_events.clear()

    yield upload_dir

    # Cleanup
    invoice_service.invoices.clear()
    invoice_service.invoice_events.clear()


def create_old_pdf(
    upload_dir: Path,
    supplier_id: str,
    invoice_number: str,
    age_days: int = 2,
):
    """
    Create a PDF file and make its modification time old.
    """

    supplier_dir = upload_dir / supplier_id
    supplier_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_path = supplier_dir / f"{invoice_number}.pdf"

    # Minimal valid PDF signature for our service
    file_path.write_bytes(
        b"%PDF-1.4\n"
    )

    old_timestamp = (
        file_path.stat().st_mtime
        - (age_days * 24 * 60 * 60)
    )

    os.utime(
        file_path,
        (old_timestamp, old_timestamp),
    )

    return file_path


def create_recent_pdf(
    upload_dir: Path,
    supplier_id: str,
    invoice_number: str,
):
    """
    Create a recent PDF file.
    """

    supplier_dir = upload_dir / supplier_id
    supplier_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_path = supplier_dir / f"{invoice_number}.pdf"

    file_path.write_bytes(
        b"%PDF-1.4\n"
    )

    return file_path


# ============================================================
# TEST 1 - NO UPLOAD DIRECTORY
# ============================================================

def test_find_orphaned_files_when_directory_does_not_exist(
    tmp_path,
    monkeypatch,
):
    """
    If the upload directory does not exist,
    no orphaned files should be returned.
    """

    upload_dir = tmp_path / "does-not-exist"

    monkeypatch.setattr(
        invoice_service,
        "UPLOAD_DIR",
        str(upload_dir),
    )

    invoice_service.invoices.clear()

    result = (
        invoice_service.find_orphaned_invoice_files(
            older_than_days=1,
        )
    )

    assert result == []


# ============================================================
# TEST 2 - INVALID AGE
# ============================================================

def test_find_orphaned_files_rejects_negative_age(
    orphan_test_setup,
):
    """
    older_than_days cannot be negative.
    """

    with pytest.raises(ValueError) as exc_info:

        invoice_service.find_orphaned_invoice_files(
            older_than_days=-1,
        )

    assert (
        "older_than_days must be greater than or equal to zero"
        in str(exc_info.value)
    )


# ============================================================
# TEST 3 - FILE WITHOUT INVOICE RECORD
# ============================================================

def test_find_orphaned_file_when_invoice_does_not_exist(
    orphan_test_setup,
):
    """
    An old PDF with no matching invoice record
    must be considered orphaned.
    """

    upload_dir = orphan_test_setup

    file_path = create_old_pdf(
        upload_dir=upload_dir,
        supplier_id="SUP001",
        invoice_number="INV001",
        age_days=2,
    )

    result = (
        invoice_service.find_orphaned_invoice_files(
            older_than_days=1,
        )
    )

    assert len(result) == 1

    orphan = result[0]

    assert orphan["invoice_number"] == "INV001"
    assert orphan["supplier_id"] == "SUP001"
    assert orphan["file_name"] == "INV001.pdf"
    assert orphan["file_path"] == str(file_path)
    assert orphan["invoice_status"] is None
    assert (
        orphan["reason"]
        == "No matching invoice record exists."
    )


# ============================================================
# TEST 4 - APPROVED INVOICE IS NOT ORPHANED
# ============================================================

def test_approved_invoice_file_is_not_orphaned(
    orphan_test_setup,
):
    """
    Approved invoices are terminal.
    Their files must not be considered orphaned.
    """

    upload_dir = orphan_test_setup

    file_path = create_old_pdf(
        upload_dir,
        "SUP001",
        "INV002",
        age_days=2,
    )

    invoice_service.invoices[
        ("SUP001", "INV002")
    ] = {
        "invoice_number": "INV002",
        "supplier_id": "SUP001",
        "status": InvoiceStatus.approved,
        "document_url": str(file_path),
    }

    result = (
        invoice_service.find_orphaned_invoice_files(
            older_than_days=1,
        )
    )

    assert result == []


# ============================================================
# TEST 5 - REJECTED INVOICE IS NOT ORPHANED
# ============================================================

def test_rejected_invoice_file_is_not_orphaned(
    orphan_test_setup,
):
    """
    Rejected invoices are terminal.
    Their files must not be considered orphaned.
    """

    upload_dir = orphan_test_setup

    file_path = create_old_pdf(
        upload_dir,
        "SUP001",
        "INV003",
        age_days=2,
    )

    invoice_service.invoices[
        ("SUP001", "INV003")
    ] = {
        "invoice_number": "INV003",
        "supplier_id": "SUP001",
        "status": InvoiceStatus.rejected,
        "document_url": str(file_path),
    }

    result = (
        invoice_service.find_orphaned_invoice_files(
            older_than_days=1,
        )
    )

    assert result == []


# ============================================================
# TEST 6 - SUBMITTED OLD FILE IS ORPHANED
# ============================================================

def test_submitted_old_invoice_file_is_orphaned(
    orphan_test_setup,
):
    """
    A submitted invoice is non-terminal.
    If its PDF is old, it is considered orphaned.
    """

    upload_dir = orphan_test_setup

    file_path = create_old_pdf(
        upload_dir,
        "SUP001",
        "INV004",
        age_days=2,
    )

    invoice_service.invoices[
        ("SUP001", "INV004")
    ] = {
        "invoice_number": "INV004",
        "supplier_id": "SUP001",
        "status": InvoiceStatus.submitted,
        "document_url": str(file_path),
    }

    result = (
        invoice_service.find_orphaned_invoice_files(
            older_than_days=1,
        )
    )

    assert len(result) == 1

    orphan = result[0]

    assert orphan["invoice_number"] == "INV004"
    assert orphan["invoice_status"] == "submitted"

    assert (
        "not in a terminal state"
        in orphan["reason"]
    )


# ============================================================
# TEST 7 - DISPUTED FILE WITHOUT DOCUMENT ASSOCIATION
# ============================================================

def test_non_terminal_invoice_without_document_url_is_orphaned(
    orphan_test_setup,
):
    """
    If the invoice exists but document_url is missing,
    the physical PDF has no registered association.
    """

    upload_dir = orphan_test_setup

    file_path = create_old_pdf(
        upload_dir,
        "SUP002",
        "INV005",
        age_days=2,
    )

    invoice_service.invoices[
        ("SUP002", "INV005")
    ] = {
        "invoice_number": "INV005",
        "supplier_id": "SUP002",
        "status": InvoiceStatus.disputed,
        "document_url": None,
    }

    result = (
        invoice_service.find_orphaned_invoice_files(
            older_than_days=1,
        )
    )

    assert len(result) == 1

    orphan = result[0]

    assert orphan["invoice_number"] == "INV005"
    assert orphan["invoice_status"] == "disputed"

    assert (
        "file is not registered"
        in orphan["reason"]
    )


# ============================================================
# TEST 8 - DOCUMENT PATH MISMATCH
# ============================================================

def test_invoice_file_with_wrong_document_path_is_orphaned(
    orphan_test_setup,
):
    """
    If invoice.document_url points to another file,
    the physical file is orphaned.
    """

    upload_dir = orphan_test_setup

    file_path = create_old_pdf(
        upload_dir,
        "SUP003",
        "INV006",
        age_days=2,
    )

    wrong_path = (
        upload_dir
        / "SUP003"
        / "different-file.pdf"
    )

    invoice_service.invoices[
        ("SUP003", "INV006")
    ] = {
        "invoice_number": "INV006",
        "supplier_id": "SUP003",
        "status": InvoiceStatus.submitted,
        "document_url": str(wrong_path),
    }

    result = (
        invoice_service.find_orphaned_invoice_files(
            older_than_days=1,
        )
    )

    assert len(result) == 1

    orphan = result[0]

    assert orphan["invoice_number"] == "INV006"

    assert (
        "File path does not match"
        in orphan["reason"]
    )

    assert file_path.exists()


# ============================================================
# TEST 9 - RECENT FILE IS NOT ORPHANED
# ============================================================

def test_recent_invoice_file_is_not_orphaned(
    orphan_test_setup,
):
    """
    Files newer than older_than_days must be ignored.
    """

    upload_dir = orphan_test_setup

    file_path = create_recent_pdf(
        upload_dir,
        "SUP004",
        "INV007",
    )

    result = (
        invoice_service.find_orphaned_invoice_files(
            older_than_days=1,
        )
    )

    assert result == []

    assert file_path.exists()


# ============================================================
# TEST 10 - PURGE ORPHANED FILE
# ============================================================

def test_purge_deletes_orphaned_file(
    orphan_test_setup,
):
    """
    purge_orphaned_invoice_files() must physically
    delete orphaned PDF files.
    """

    upload_dir = orphan_test_setup

    file_path = create_old_pdf(
        upload_dir,
        "SUP005",
        "INV008",
        age_days=2,
    )

    assert file_path.exists()

    result = (
        invoice_service.purge_orphaned_invoice_files(
            older_than_days=1,
        )
    )

    assert result["total"] == 1
    assert result["deleted"] == 1

    assert len(result["files"]) == 1

    assert (
        result["files"][0]["invoice_number"]
        == "INV008"
    )

    assert not file_path.exists()


# ============================================================
# TEST 11 - PURGE DOES NOT DELETE APPROVED FILE
# ============================================================

def test_purge_does_not_delete_approved_file(
    orphan_test_setup,
):
    """
    Approved invoice documents must remain untouched.
    """

    upload_dir = orphan_test_setup

    file_path = create_old_pdf(
        upload_dir,
        "SUP006",
        "INV009",
        age_days=2,
    )

    invoice_service.invoices[
        ("SUP006", "INV009")
    ] = {
        "invoice_number": "INV009",
        "supplier_id": "SUP006",
        "status": InvoiceStatus.approved,
        "document_url": str(file_path),
    }

    result = (
        invoice_service.purge_orphaned_invoice_files(
            older_than_days=1,
        )
    )

    assert result["total"] == 0
    assert result["deleted"] == 0

    assert file_path.exists()


# ============================================================
# TEST 12 - PURGE DOES NOT DELETE RECENT ORPHAN
# ============================================================

def test_purge_does_not_delete_recent_file(
    orphan_test_setup,
):
    """
    A recent file must not be deleted even if
    there is no invoice record.
    """

    upload_dir = orphan_test_setup

    file_path = create_recent_pdf(
        upload_dir,
        "SUP007",
        "INV010",
    )

    result = (
        invoice_service.purge_orphaned_invoice_files(
            older_than_days=1,
        )
    )

    assert result["total"] == 0
    assert result["deleted"] == 0

    assert file_path.exists()


# ============================================================
# TEST 13 - PURGE MULTIPLE ORPHANED FILES
# ============================================================

def test_purge_multiple_orphaned_files(
    orphan_test_setup,
):
    """
    Multiple orphaned files should all be deleted.
    """

    upload_dir = orphan_test_setup

    file1 = create_old_pdf(
        upload_dir,
        "SUP008",
        "INV011",
        age_days=3,
    )

    file2 = create_old_pdf(
        upload_dir,
        "SUP008",
        "INV012",
        age_days=3,
    )

    file3 = create_old_pdf(
        upload_dir,
        "SUP009",
        "INV013",
        age_days=3,
    )

    result = (
        invoice_service.purge_orphaned_invoice_files(
            older_than_days=1,
        )
    )

    assert result["total"] == 3
    assert result["deleted"] == 3

    assert not file1.exists()
    assert not file2.exists()
    assert not file3.exists()


# ============================================================
# TEST 14 - PURGE MIXED FILES
# ============================================================

def test_purge_only_deletes_orphaned_files(
    orphan_test_setup,
):
    """
    Verify that purge deletes only orphaned files.

    Old orphan       -> DELETE
    Old approved     -> KEEP
    Recent orphan    -> KEEP
    """

    upload_dir = orphan_test_setup

    # --------------------------------------------------------
    # Old orphan
    # --------------------------------------------------------

    orphan_file = create_old_pdf(
        upload_dir,
        "SUP010",
        "INV014",
        age_days=3,
    )

    # --------------------------------------------------------
    # Old approved invoice
    # --------------------------------------------------------

    approved_file = create_old_pdf(
        upload_dir,
        "SUP010",
        "INV015",
        age_days=3,
    )

    invoice_service.invoices[
        ("SUP010", "INV015")
    ] = {
        "invoice_number": "INV015",
        "supplier_id": "SUP010",
        "status": InvoiceStatus.approved,
        "document_url": str(approved_file),
    }

    # --------------------------------------------------------
    # Recent orphan
    # --------------------------------------------------------

    recent_file = create_recent_pdf(
        upload_dir,
        "SUP010",
        "INV016",
    )

    # --------------------------------------------------------
    # Execute purge
    # --------------------------------------------------------

    result = (
        invoice_service.purge_orphaned_invoice_files(
            older_than_days=1,
        )
    )

    # Only old orphan should be deleted
    assert result["total"] == 1
    assert result["deleted"] == 1

    assert not orphan_file.exists()

    # Approved file remains
    assert approved_file.exists()

    # Recent file remains
    assert recent_file.exists()