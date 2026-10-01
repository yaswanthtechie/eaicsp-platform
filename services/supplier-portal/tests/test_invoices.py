from io import BytesIO
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import verify_token
from app.schemas.invoice import InvoiceStatus
from app.services.purchase_order_service import (
    purchase_orders,
    po_events,
)
from app.services.invoice_service import (
    invoices,
    invoice_events,
)
from app.services import invoice_service
from app.services.document_storage_service import (
    DocumentStorageError,
    DocumentDownloadError,
)
from app.services.po_p2p_state_machine import (
    P2PState,
    p2p_states,
)
from app.services.supplier_onboarding_service import (
    suppliers,
    SupplierOnboardingStatus,
)

client = TestClient(app)


# ============================================================
# MINIO TEST HELPERS
# ============================================================

def make_minio_object(
    object_name: str,
    *,
    age_days: float = 2,
    size: int = 100,
):
    """
    Create a lightweight fake MinIO object for unit tests.

    This replaces the old local-filesystem Path/File usage.
    """

    return SimpleNamespace(
        object_name=object_name,
        last_modified=(
            datetime.now(timezone.utc)
            - timedelta(days=age_days)
        ),
        size=size,
    )


def invoice_object_key(
    supplier_id: str = "SUP001",
    invoice_number: str = "INV1001",
) -> str:
    """
    Return the canonical MinIO object key for an invoice.
    """

    return (
        f"suppliers/{supplier_id}/"
        f"invoices/{invoice_number}.pdf"
    )


def valid_pdf_bytes() -> bytes:
    """
    Minimal PDF payload used by invoice upload tests.
    """

    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n"
        b"<< /Type /Catalog >>\n"
        b"endobj\n"
        b"%%EOF"
    )


# ============================================================
# TEST AUTHENTICATION USERS
# ============================================================

SUPPLIER_1_USER = {
    "valid": True,
    "user_id": 8,
    "email": "supplier@company.com",
    "full_name": "Supplier User",
    "role": "supplier",
    "supplier_id": "SUP001",
    "is_active": True,
}


SUPPLIER_2_USER = {
    "valid": True,
    "user_id": 9,
    "email": "supplier2@company.com",
    "full_name": "Supplier Two",
    "role": "supplier",
    "supplier_id": "SUP002",
    "is_active": True,
}


SUPPLIER_123_USER = {
    "valid": True,
    "user_id": 10,
    "email": "supplier123@company.com",
    "full_name": "Supplier 123",
    "role": "supplier",
    "supplier_id": "SUP123",
    "is_active": True,
}


COMPLIANCE_USER = {
    "valid": True,
    "user_id": 6,
    "email": "compliance@company.com",
    "full_name": "Compliance Officer",
    "role": "compliance_officer",
    "supplier_id": None,
    "is_active": True,
}


PROCUREMENT_USER = {
    "valid": True,
    "user_id": 4,
    "email": "procurementmanager@company.com",
    "full_name": "Procurement Manager",
    "role": "procurement_manager",
    "supplier_id": None,
    "is_active": True,
}


SUPPLIER_NO_ID_USER = {
    "valid": True,
    "user_id": 100,
    "email": "supplier-no-id@example.com",
    "full_name": "Supplier Without ID",
    "role": "supplier",
    "supplier_id": None,
    "is_active": True,
}


def authenticate_as(user):
    """
    Change the authenticated test user.
    """

    async def mock_verify_token():
        return user

    app.dependency_overrides[verify_token] = mock_verify_token


# ============================================================
# TEST SETUP
# ============================================================

@pytest.fixture(autouse=True)
def reset_data():
    """
    Reset all in-memory application data before every test.

    Invoice documents are stored in MinIO, so this fixture
    intentionally does NOT manipulate the old local uploads/
    directory.
    """

    purchase_orders.clear()
    invoices.clear()
    po_events.clear()
    invoice_events.clear()
    p2p_states.clear()
    suppliers.clear()

    suppliers.update(
        {
            "SUP001": {
                "supplier_id": "SUP001",
                "status": SupplierOnboardingStatus.active,
            },
            "SUP002": {
                "supplier_id": "SUP002",
                "status": SupplierOnboardingStatus.active,
            },
            "SUP123": {
                "supplier_id": "SUP123",
                "status": SupplierOnboardingStatus.active,
            },
        }
    )

    app.dependency_overrides.clear()

    yield

    purchase_orders.clear()
    invoices.clear()
    po_events.clear()
    invoice_events.clear()
    p2p_states.clear()
    suppliers.clear()

    app.dependency_overrides.clear()


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

    PO creation is a procurement_manager operation.
    """

    authenticate_as(PROCUREMENT_USER)

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

    authenticate_as(PROCUREMENT_USER)

    response = client.post(
        f"/api/v1/purchase-orders/{po_number}/transition",
        json={
            "actor": "buyer",
            "target_state": "sent",
        },
    )

    assert response.status_code == 200, response.text

    po = purchase_orders[po_number]
    supplier_id = po["supplier_id"]

    if supplier_id == "SUP001":
        authenticate_as(SUPPLIER_1_USER)

    elif supplier_id == "SUP002":
        authenticate_as(SUPPLIER_2_USER)

    elif supplier_id == "SUP123":
        authenticate_as(SUPPLIER_123_USER)

    else:
        raise ValueError(
            f"No test user configured for supplier_id={supplier_id}"
        )

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
    Create a PO and move it to:

        draft -> sent -> acknowledged
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


def create_received_po(
    po_number="PO1001",
    supplier_id="SUP001",
    item_code="LAPTOP",
    quantity=1,
    unit_price=50000,
):
    """
    Prepare a PO at P2P 'received' state for invoice tests.

    This is intentionally a test helper and does not modify
    the production P2P workflow.
    """

    create_acknowledged_po(
        po_number=po_number,
        supplier_id=supplier_id,
        item_code=item_code,
        quantity=quantity,
        unit_price=unit_price,
    )

    p2p_states[po_number] = P2PState.received

    return purchase_orders[po_number]


def create_fulfilled_po(
    po_number="PO1001",
    supplier_id="SUP001",
    item_code="LAPTOP",
    quantity=1,
    unit_price=50000,
):
    """
    Create a PO and move its business status through:

        draft -> sent -> acknowledged -> fulfilled

    Note:
        PO business status and P2P workflow state are separate.
    """

    create_acknowledged_po(
        po_number=po_number,
        supplier_id=supplier_id,
        item_code=item_code,
        quantity=quantity,
        unit_price=unit_price,
    )

    authenticate_as(PROCUREMENT_USER)

    response = client.post(
        f"/api/v1/purchase-orders/{po_number}/transition",
        json={
            "actor": "buyer",
            "target_state": "fulfilled",
        },
    )

    assert response.status_code == 200, response.text

    return response.json()


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
    Create an invoice using the invoice API.
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
    Create a valid submitted invoice.

    The PO is prepared at P2P state 'received' because
    invoice creation requires goods receipt first.
    """

    create_received_po()

    authenticate_as(SUPPLIER_1_USER)

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
):
    """
    Call the invoice transition API.
    """

    return client.post(
        f"/api/v1/invoices/{supplier_id}/{invoice_number}/transition",
        json={
            "target_state": target_state,
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
    """
    Call the invoice adjustment API.
    """

    return client.post(
        f"/api/v1/invoices/{supplier_id}/{invoice_number}/adjust",
        json={
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


# ============================================================
# INVOICE STATE MACHINE TESTS
# ============================================================

def test_submitted_to_approved():
    create_submitted_invoice()

    authenticate_as(SUPPLIER_1_USER)

    response = transition_invoice(
        "INV1001",
        "approved",
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["status"] == "approved"


def test_submitted_to_disputed():
    create_submitted_invoice()

    authenticate_as(SUPPLIER_1_USER)

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

    # Audit identity comes from authenticated supplier user.
    assert data["dispute"]["actor_id"] == "8"
    assert data["dispute"]["actor_name"] == "Supplier User"
    assert data["dispute"]["role"] == "supplier"

    assert data["dispute"]["timestamp"] is not None


def test_submitted_to_rejected():
    create_submitted_invoice()

    authenticate_as(SUPPLIER_1_USER)

    response = transition_invoice(
        "INV1001",
        "rejected",
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["status"] == "rejected"


def test_adjusted_to_rejected():
    create_submitted_invoice()

    # --------------------------------------------------------
    # submitted -> disputed
    # Supplier can dispute the invoice.
    # --------------------------------------------------------

    authenticate_as(SUPPLIER_1_USER)

    response = transition_invoice(
        "INV1001",
        "disputed",
        reason="Invoice has an incorrect amount.",
    )

    assert response.status_code == 200, response.text

    # --------------------------------------------------------
    # disputed -> adjusted
    # Only Compliance Officer can adjust.
    # --------------------------------------------------------

    authenticate_as(COMPLIANCE_USER)

    response = adjust_invoice_api(
        invoice_number="INV1001",
        quantity=1,
        unit_price=50000,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["status"] == "adjusted"

    # Adjustment audit must use authenticated Compliance Officer.
    assert data["adjustment"]["actor_id"] == "6"
    assert data["adjustment"]["actor_name"] == "Compliance Officer"
    assert data["adjustment"]["role"] == "compliance_officer"

    # --------------------------------------------------------
    # adjusted -> rejected
    # Switch back to supplier.
    # --------------------------------------------------------

    authenticate_as(SUPPLIER_1_USER)

    response = transition_invoice(
        "INV1001",
        "rejected",
        reason="The adjustment is still incorrect.",
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected"


def test_disputed_to_approved():
    create_submitted_invoice()

    # --------------------------------------------------------
    # submitted -> disputed
    # Supplier disputes the invoice.
    # --------------------------------------------------------

    authenticate_as(SUPPLIER_1_USER)

    response = transition_invoice(
        "INV1001",
        "disputed",
        reason="Incorrect amount.",
    )

    assert response.status_code == 200, response.text

    # --------------------------------------------------------
    # disputed -> approved
    # --------------------------------------------------------

    response = transition_invoice(
        "INV1001",
        "approved",
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["status"] == "approved"

    assert data["dispute"]["resolution"] == "approved"

    # Resolution audit comes from authenticated user.
    assert data["dispute"]["resolved_by"] == "8"

    assert data["dispute"]["resolved_at"] is not None


def test_disputed_to_rejected():
    create_submitted_invoice()

    # --------------------------------------------------------
    # submitted -> disputed
    # Supplier disputes the invoice.
    # --------------------------------------------------------

    authenticate_as(SUPPLIER_1_USER)

    response = transition_invoice(
        "INV1001",
        "disputed",
        reason="Incorrect invoice.",
    )

    assert response.status_code == 200, response.text

    # --------------------------------------------------------
    # disputed -> rejected
    # --------------------------------------------------------

    response = transition_invoice(
        "INV1001",
        "rejected",
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["status"] == "rejected"

    assert data["dispute"]["resolution"] == "rejected"

    # Resolution audit comes from authenticated user.
    assert data["dispute"]["resolved_by"] == "8"

    assert data["dispute"]["resolved_at"] is not None


def test_disputed_to_adjusted_to_approved():
    create_submitted_invoice()

    # --------------------------------------------------------
    # submitted -> disputed
    # Supplier disputes the invoice.
    # --------------------------------------------------------

    authenticate_as(SUPPLIER_1_USER)

    response = transition_invoice(
        "INV1001",
        "disputed",
        reason="Incorrect quantity.",
    )

    assert response.status_code == 200, response.text

    # --------------------------------------------------------
    # disputed -> adjusted
    # Compliance Officer performs adjustment.
    # --------------------------------------------------------

    authenticate_as(COMPLIANCE_USER)

    response = adjust_invoice_api(
        invoice_number="INV1001",
        quantity=1,
        unit_price=50000,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["status"] == "adjusted"

    # Verify authenticated Compliance Officer audit identity.
    assert data["adjustment"]["actor_id"] == "6"
    assert data["adjustment"]["actor_name"] == "Compliance Officer"
    assert data["adjustment"]["role"] == "compliance_officer"

    # --------------------------------------------------------
    # adjusted -> approved
    # --------------------------------------------------------

    authenticate_as(SUPPLIER_1_USER)

    response = transition_invoice(
        "INV1001",
        "approved",
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["status"] == "approved"


def test_dispute_requires_reason():
    create_submitted_invoice()

    authenticate_as(SUPPLIER_1_USER)

    response = transition_invoice(
        "INV1001",
        "disputed",
    )

    assert response.status_code == 400, response.text

    detail = response.json()["detail"]

    assert "reason is required" in detail.lower()

    # --------------------------------------------------------
    # Invoice must remain submitted.
    # --------------------------------------------------------

    invoice_key = ("SUP001", "INV1001")

    assert (
        invoices[invoice_key]["status"]
        == InvoiceStatus.submitted
    )


def test_dispute_rejects_blank_reason():
    create_submitted_invoice()

    authenticate_as(SUPPLIER_1_USER)

    response = transition_invoice(
        "INV1001",
        "disputed",
        reason="   ",
    )

    assert response.status_code == 400, response.text

    assert "reason is required" in (
        response.json()["detail"].lower()
    )

    # --------------------------------------------------------
    # Invoice must remain submitted.
    # --------------------------------------------------------

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
        # ----------------------------------------------------
        # submitted
        # ----------------------------------------------------

        ("submitted", "submitted"),
        ("submitted", "adjusted"),

        # ----------------------------------------------------
        # disputed
        # ----------------------------------------------------

        ("disputed", "submitted"),
        ("disputed", "disputed"),

        # ----------------------------------------------------
        # approved - terminal
        # ----------------------------------------------------

        ("approved", "submitted"),
        ("approved", "disputed"),
        ("approved", "rejected"),
        ("approved", "adjusted"),

        # ----------------------------------------------------
        # rejected - terminal
        # ----------------------------------------------------

        ("rejected", "submitted"),
        ("rejected", "disputed"),
        ("rejected", "approved"),
        ("rejected", "adjusted"),

        # ----------------------------------------------------
        # adjusted
        # ----------------------------------------------------

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
    # Start as supplier
    # --------------------------------------------------------

    authenticate_as(SUPPLIER_1_USER)

    # --------------------------------------------------------
    # Move invoice to the required current state
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

        # ----------------------------------------------------
        # submitted -> disputed
        # ----------------------------------------------------

        authenticate_as(SUPPLIER_1_USER)

        response = transition_invoice(
            "INV1001",
            "disputed",
            reason="Test dispute.",
        )

        assert response.status_code == 200, response.text

        # ----------------------------------------------------
        # disputed -> adjusted
        # Compliance officer is required
        # ----------------------------------------------------

        authenticate_as(COMPLIANCE_USER)

        response = adjust_invoice_api(
            invoice_number="INV1001",
            quantity=1,
            unit_price=50000,
        )

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "adjusted"

        # ----------------------------------------------------
        # Switch back to supplier
        # ----------------------------------------------------

        authenticate_as(SUPPLIER_1_USER)

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
    authenticate_as(SUPPLIER_1_USER)

    response = transition_invoice(
        "INV9999",
        "approved",
    )

    assert response.status_code == 404, response.text

    assert response.json()["detail"] == (
        "Invoice not found."
    )

def test_rejected_invoice_quantity_is_not_counted():
    create_received_po(
        quantity=10,
        unit_price=50000,
    )

    # --------------------------------------------------------
    # First invoice consumes all 10 units
    # --------------------------------------------------------

    response = create_sample_invoice(
        invoice_number="INV1001",
        quantity=10,
        amount=500000,
    )

    assert response.status_code == 201, response.text

    # --------------------------------------------------------
    # Reject the invoice
    # --------------------------------------------------------

    authenticate_as(SUPPLIER_1_USER)

    response = transition_invoice(
        invoice_number="INV1001",
        target_state="rejected",
        reason="Invoice is incorrect.",
    )

    assert response.status_code == 200, response.text

    # --------------------------------------------------------
    # The rejected invoice must no longer consume quantity.
    #
    # The first invoice moved the P2P state from:
    #
    #     received -> invoiced
    #
    # This test is specifically testing invoice quantity
    # reuse after rejection, so prepare the P2P state again
    # at 'received' for the replacement invoice.
    # --------------------------------------------------------

    p2p_states["PO1001"] = P2PState.received

    # --------------------------------------------------------
    # Another invoice for the same 10 units must be allowed.
    # --------------------------------------------------------

    response = create_sample_invoice(
        invoice_number="INV1002",
        quantity=10,
        amount=500000,
    )

    assert response.status_code == 201, response.text


def test_invoice_unit_price_exactly_5_percent_below():
    create_received_po(
        unit_price=50000,
    )

    response = create_sample_invoice(
        invoice_number="INV9101",
        unit_price=47500,
        amount=47500,
    )

    assert response.status_code == 201, response.text


def test_invoice_unit_price_exactly_5_percent_above():
    create_received_po(
        unit_price=50000,
    )

    response = create_sample_invoice(
        invoice_number="INV9102",
        unit_price=52500,
        amount=52500,
    )

    assert response.status_code == 201, response.text



def test_invoice_unit_price_just_below_5_percent_boundary():
    create_received_po(
        unit_price=50000,
    )

    response = create_sample_invoice(
        invoice_number="INV9103",
        unit_price=47499.99,
        amount=47499.99,
    )

    assert response.status_code in (200, 201), response.text

    data = response.json()

    assert data["invoice_number"] == "INV9103"
    assert data["items"][0]["unit_price"] == 47499.99


def test_invoice_unit_price_just_above_5_percent_boundary():
    create_received_po(
        unit_price=50000,
    )

    response = create_sample_invoice(
        invoice_number="INV9104",
        unit_price=52500.01,
        amount=52500.01,
    )

    assert response.status_code in (200, 201), response.text

    data = response.json()

    assert data["invoice_number"] == "INV9104"
    assert data["items"][0]["unit_price"] == 52500.01


def test_invoice_history_is_created_on_transition():
    create_submitted_invoice()

    authenticate_as(SUPPLIER_1_USER)

    response = transition_invoice(
        "INV1001",
        "approved",
        reason="Invoice verified.",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "approved"
    assert len(data["history"]) == 1

    history = data["history"][0]

    assert history["from_status"] == "submitted"
    assert history["to_status"] == "approved"
    assert history["actor_id"] == "8"
    assert history["actor_name"] == "Supplier User"
    assert history["role"] == "supplier"
    assert history["reason"] == "Invoice verified."
    assert "timestamp" in history



def test_invoice_history_tracks_multiple_transitions():
    create_submitted_invoice()

    # --------------------------------------------------------
    # submitted -> disputed
    # --------------------------------------------------------

    authenticate_as(SUPPLIER_1_USER)

    response = transition_invoice(
        "INV1001",
        "disputed",
        reason="Incorrect quantity.",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "disputed"
    assert len(data["history"]) == 1

    first_history = data["history"][0]

    assert first_history["from_status"] == "submitted"
    assert first_history["to_status"] == "disputed"
    assert first_history["actor_id"] == "8"
    assert first_history["actor_name"] == "Supplier User"
    assert first_history["role"] == "supplier"
    assert first_history["reason"] == "Incorrect quantity."
    assert "timestamp" in first_history

    # --------------------------------------------------------
    # disputed -> approved
    # --------------------------------------------------------

    authenticate_as(SUPPLIER_1_USER)

    response = transition_invoice(
        "INV1001",
        "approved",
        reason="Dispute resolved.",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "approved"
    assert len(data["history"]) == 2

    first_history = data["history"][0]
    second_history = data["history"][1]

    # First transition
    assert first_history["from_status"] == "submitted"
    assert first_history["to_status"] == "disputed"
    assert first_history["actor_id"] == "8"
    assert first_history["actor_name"] == "Supplier User"
    assert first_history["role"] == "supplier"
    assert first_history["reason"] == "Incorrect quantity."

    # Second transition
    assert second_history["from_status"] == "disputed"
    assert second_history["to_status"] == "approved"
    assert second_history["actor_id"] == "8"
    assert second_history["actor_name"] == "Supplier User"
    assert second_history["role"] == "supplier"
    assert second_history["reason"] == "Dispute resolved."
    assert "timestamp" in second_history

# ============================================================
# INVOICE DOCUMENT TESTS
# ============================================================

def valid_pdf():
    return BytesIO(
        b"%PDF-1.4\n"
        b"1 0 obj\n"
        b"<< /Type /Catalog >>\n"
        b"endobj\n"
        b"%%EOF"
    )


def test_valid_pdf_with_renamed_extension_is_accepted():
    create_received_po()

    response = create_sample_invoice(
        invoice_number="INV9201",
    )

    assert response.status_code == 201, response.text

    authenticate_as(SUPPLIER_1_USER)

    expected_key = (
        "suppliers/SUP001/invoices/INV9201.pdf"
    )

    with patch.object(
        invoice_service.document_storage_service,
        "upload_invoice_document",
        return_value=expected_key,
    ) as mock_upload:
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

    # Public API URL remains stable.
    assert data["document_url"] == (
        "/api/v1/invoices/SUP001/INV9201/document"
    )

    # Internal MinIO object key is not exposed
    # through the InvoiceResponse.
    assert "document_path" not in data

    # Verify the invoice record stores the MinIO
    # object key rather than a local filesystem path.
    assert invoices[
        ("SUP001", "INV9201")
    ]["document_path"] == expected_key

    mock_upload.assert_called_once()


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
    create_received_po()

    response = create_sample_invoice(
        invoice_number="INV9301",
    )

    assert response.status_code == 201, response.text

    authenticate_as(SUPPLIER_1_USER)

    with patch.object(
        invoice_service.document_storage_service,
        "upload_invoice_document",
    ) as mock_upload:
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

    assert response.status_code == 400, response.text

    assert response.json()["detail"] == (
        "Invalid PDF signature."
    )

    # Invalid PDF must never reach MinIO.
    mock_upload.assert_not_called()


def test_valid_pdf_with_wrong_content_type_rejected():
    create_received_po()

    response = create_sample_invoice(
        invoice_number="INV9401",
    )

    assert response.status_code == 201, response.text

    authenticate_as(SUPPLIER_1_USER)

    with patch.object(
        invoice_service.document_storage_service,
        "upload_invoice_document",
    ) as mock_upload:
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

    assert response.status_code == 400, response.text

    assert response.json()["detail"] == (
        "Only PDF files are allowed."
    )

    # Invalid content type must never reach MinIO.
    mock_upload.assert_not_called()


def test_upload_invoice_pdf_stores_minio_object_key():
    create_submitted_invoice(
        invoice_number="INV9501",
    )

    authenticate_as(SUPPLIER_1_USER)

    expected_key = (
        "suppliers/SUP001/invoices/INV9501.pdf"
    )

    with patch.object(
        invoice_service.document_storage_service,
        "upload_invoice_document",
        return_value=expected_key,
    ) as mock_upload:
        response = client.post(
            "/api/v1/invoices/SUP001/INV9501/document",
            files={
                "file": (
                    "invoice.pdf",
                    valid_pdf(),
                    "application/pdf",
                )
            },
        )

    assert response.status_code == 200, response.text

    invoice = invoices[
        ("SUP001", "INV9501")
    ]

    assert invoice["document_path"] == expected_key

    assert invoice["document_url"] == (
        "/api/v1/invoices/SUP001/INV9501/document"
    )

    mock_upload.assert_called_once()


def test_invoice_document_uses_supplier_scoped_minio_key():
    create_received_po(
        po_number="PO1234",
        supplier_id="SUP123",
    )

    authenticate_as(SUPPLIER_123_USER)

    response = create_sample_invoice(
        invoice_number="INV9601",
        po_number="PO1234",
        supplier_id="SUP123",
    )

    assert response.status_code == 201, response.text

    expected_key = (
        "suppliers/SUP123/invoices/INV9601.pdf"
    )

    with patch.object(
        invoice_service.document_storage_service,
        "upload_invoice_document",
        return_value=expected_key,
    ) as mock_upload:
        response = client.post(
            "/api/v1/invoices/SUP123/INV9601/document",
            files={
                "file": (
                    "invoice.pdf",
                    valid_pdf(),
                    "application/pdf",
                )
            },
        )

    assert response.status_code == 200, response.text

    assert invoices[
        ("SUP123", "INV9601")
    ]["document_path"] == expected_key

    mock_upload.assert_called_once()


def test_supplier_cannot_upload_document_for_another_supplier():
    create_submitted_invoice(
        invoice_number="INV9701",
    )

    authenticate_as(SUPPLIER_2_USER)

    with patch.object(
        invoice_service.document_storage_service,
        "upload_invoice_document",
    ) as mock_upload:
        response = client.post(
            "/api/v1/invoices/SUP001/INV9701/document",
            files={
                "file": (
                    "invoice.pdf",
                    valid_pdf(),
                    "application/pdf",
                )
            },
        )

    assert response.status_code == 403, response.text

    # Authorization must happen before MinIO upload.
    mock_upload.assert_not_called()

def test_download_invoice_document_returns_presigned_url():
    create_submitted_invoice(
        invoice_number="INV9801",
    )

    object_key = (
        "suppliers/SUP001/invoices/INV9801.pdf"
    )

    invoices[
        ("SUP001", "INV9801")
    ]["document_path"] = object_key

    authenticate_as(SUPPLIER_1_USER)

    with patch.object(
        invoice_service.document_storage_service,
        "object_exists",
        return_value=True,
    ) as mock_exists:

        with patch.object(
            invoice_service.document_storage_service,
            "generate_download_url",
            return_value="http://minio/presigned-url",
        ) as mock_download:

            response = client.get(
                "/api/v1/invoices/SUP001/INV9801/document"
            )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["invoice_number"] == "INV9801"
    assert data["supplier_id"] == "SUP001"
    assert data["file_name"] == "INV9801.pdf"
    assert data["download_url"] == (
        "http://minio/presigned-url"
    )
    assert data["expires_in_seconds"] > 0

    mock_exists.assert_called_once_with(
        object_key=object_key,
    )

    mock_download.assert_called_once_with(
        object_key=object_key,
    )


def test_supplier_cannot_download_other_supplier_document():
    create_submitted_invoice(
        invoice_number="INV9901",
    )

    invoices[
        ("SUP001", "INV9901")
    ]["document_path"] = (
        "suppliers/SUP001/invoices/INV9901.pdf"
    )

    authenticate_as(SUPPLIER_2_USER)

    with patch.object(
        invoice_service.document_storage_service,
        "generate_download_url",
    ) as mock_download:
        response = client.get(
            "/api/v1/invoices/SUP001/INV9901/document"
        )

    assert response.status_code == 403, response.text

    # Cross-supplier access must be rejected before
    # a presigned URL is generated.
    mock_download.assert_not_called()


def test_download_invoice_without_document_returns_404():
    create_submitted_invoice(
        invoice_number="INV9910",
    )

    invoices[
        ("SUP001", "INV9910")
    ]["document_path"] = None

    authenticate_as(SUPPLIER_1_USER)

    with patch.object(
        invoice_service.document_storage_service,
        "generate_download_url",
    ) as mock_download:
        response = client.get(
            "/api/v1/invoices/SUP001/INV9910/document"
        )

    assert response.status_code == 404, response.text

    assert response.json()["detail"] == (
        "Document not found."
    )

    mock_download.assert_not_called()


# ============================================================
# GET ALL INVOICES
# ============================================================

def test_get_all_invoices_empty():
    authenticate_as(SUPPLIER_1_USER)

    response = client.get(
        "/api/v1/invoices"
    )

    assert response.status_code == 200
    assert response.json() == []


def test_get_all_invoices():
    create_received_po(
        quantity=2
    )

    response1 = create_sample_invoice(
        invoice_number="INV1001",
        quantity=1,
        amount=50000,
    )

    assert response1.status_code == 201, response1.text

    # The first invoice moves the P2P state to
    # 'invoiced'. Prepare the state again for the
    # second invoice.
    p2p_states["PO1001"] = P2PState.received

    response2 = create_sample_invoice(
        invoice_number="INV1002",
        quantity=1,
        amount=50000,
    )

    assert response2.status_code == 201, response2.text

    response = client.get(
        "/api/v1/invoices"
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert len(data) == 2
    assert data[0]["invoice_number"] == "INV1001"
    assert data[1]["invoice_number"] == "INV1002"


# ============================================================
# CREATE INVOICE
# ============================================================

def test_create_invoice_success():
    create_received_po()

    response = create_sample_invoice(
        invoice_number="INV2001"
    )

    assert response.status_code == 201, response.text

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
    create_received_po()

    create_response = create_sample_invoice(
        invoice_number="INV2001"
    )

    assert create_response.status_code == 201, (
        create_response.text
    )

    authenticate_as(SUPPLIER_1_USER)

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
    authenticate_as(SUPPLIER_1_USER)

    response = client.get(
        "/api/v1/invoices/SUP001/INVALID001"
    )

    assert response.status_code == 404, response.text

    assert response.json()["detail"] == (
        "Invoice not found."
    )


# ============================================================
# DUPLICATE INVOICE
# ============================================================

def test_duplicate_invoice():
    create_received_po()

    response = create_sample_invoice(
        invoice_number="INV1001"
    )

    assert response.status_code == 201, response.text

    response = create_sample_invoice(
        invoice_number="INV1001"
    )

    assert response.status_code == 409, response.text

    assert "already exists" in (
        response.json()["detail"].lower()
    )


# ============================================================
# SAME INVOICE NUMBER FOR DIFFERENT SUPPLIER
# ============================================================

def test_same_invoice_number_different_supplier():
    # --------------------------------------------------------
    # Supplier 1 owns PO1001
    # --------------------------------------------------------

    create_received_po(
        po_number="PO1001",
        supplier_id="SUP001",
    )

    # --------------------------------------------------------
    # Supplier 2 owns PO1002
    # --------------------------------------------------------

    create_received_po(
        po_number="PO1002",
        supplier_id="SUP002",
    )

    # --------------------------------------------------------
    # Supplier 1 creates INV1001
    # --------------------------------------------------------

    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV1001",
        po_number="PO1001",
        supplier_id="SUP001",
    )

    assert response.status_code == 201, response.text

    # --------------------------------------------------------
    # Supplier 2 can also create INV1001 because invoice
    # numbers are supplier-scoped.
    # --------------------------------------------------------

    authenticate_as(SUPPLIER_2_USER)

    response = create_sample_invoice(
        invoice_number="INV1001",
        po_number="PO1002",
        supplier_id="SUP002",
    )

    assert response.status_code == 201, response.text

    assert ("SUP001", "INV1001") in invoices
    assert ("SUP002", "INV1001") in invoices

# ============================================================
# DUPLICATE INVOICE NUMBER - SAME SUPPLIER
# ============================================================

def test_duplicate_invoice_number_same_supplier():
    create_received_po(
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
    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV1001",
        po_number="PO9999",
    )

    assert response.status_code == 404, response.text

    assert response.json()["detail"] == (
        "Purchase Order 'PO9999' not found."
    )


# ============================================================
# PO IN DRAFT STATUS
# ============================================================

def test_invoice_po_in_draft_status_rejected():
    create_sample_po()

    # create_sample_po() leaves the procurement user
    # authenticated.
    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV1001",
    )

    assert response.status_code == 400, response.text

    detail = response.json()["detail"]

    assert "status" in detail.lower()
    assert "draft" in detail.lower()


# ============================================================
# PO IN SENT STATUS
# ============================================================

def test_invoice_po_in_sent_status_rejected():
    create_sample_po()

    authenticate_as(PROCUREMENT_USER)

    response = client.post(
        "/api/v1/purchase-orders/PO1001/transition",
        json={
            "actor": "buyer",
            "target_state": "sent",
        },
    )

    assert response.status_code == 200, response.text

    # Invoice creation must still be rejected because
    # the PO has not reached the required P2P received state.
    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV1001",
    )

    assert response.status_code == 400, response.text

    assert "sent" in (
        response.json()["detail"].lower()
    )


# ============================================================
# ACKNOWLEDGED PO - REJECTED BEFORE GOODS RECEIPT
# ============================================================

def test_invoice_acknowledged_po_rejected_before_receipt():
    create_acknowledged_po()

    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV1001",
    )

    # Required P2P flow:
    #
    # acknowledged
    #      ↓
    # shipped
    #      ↓
    # received
    #      ↓
    # invoice
    #
    # Therefore acknowledged alone is insufficient.

    assert response.status_code == 400, response.text

    detail = response.json()["detail"].lower()

    assert "acknowledged" in detail
    assert "received" in detail


# ============================================================
# FULFILLED PO
# ============================================================

def test_invoice_fulfilled_po_accepted():
    create_fulfilled_po()

    # PO business status is fulfilled, but the P2P workflow
    # still needs to be at received for invoice creation.
    p2p_states["PO1001"] = P2PState.received

    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV1001",
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["invoice_number"] == "INV1001"
    assert data["supplier_id"] == "SUP001"
    assert data["amount"] == 50000


# ============================================================
# INVALID ITEM
# ============================================================

def test_invoice_item_not_in_po():
    create_received_po(
        item_code="LAPTOP",
    )

    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV1001",
        item_code="MOUSE",
    )

    assert response.status_code == 400, response.text

    detail = response.json()["detail"]

    assert "does not exist" in detail


# ============================================================
# QUANTITY GREATER THAN PO
# ============================================================

def test_invoice_quantity_exceeds_po_quantity():
    create_received_po(
        quantity=5,
    )

    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV1001",
        quantity=6,
    )

    assert response.status_code == 400, response.text

    detail = response.json()["detail"]

    assert "cannot exceed" in detail


# ============================================================
# PARTIAL INVOICE
# ============================================================

def test_partial_invoice():
    create_received_po(
        quantity=10,
    )

    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV1001",
        quantity=4,
        unit_price=50000,
        amount=200000,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["invoice_number"] == "INV1001"
    assert data["amount"] == 200000

    assert len(data["items"]) == 1
    assert data["items"][0]["quantity"] == 4
    assert data["items"][0]["unit_price"] == 50000

    # Document upload is a separate operation.
    invoice = invoices[
        ("SUP001", "INV1001")
    ]

    assert invoice["document_path"] is None


# ============================================================
# MULTIPLE PARTIAL INVOICES
# ============================================================

def test_multiple_partial_invoices():
    create_received_po(
        quantity=10,
    )

    authenticate_as(SUPPLIER_1_USER)

    # --------------------------------------------------------
    # First partial invoice: 4 / 10
    # --------------------------------------------------------

    response1 = create_sample_invoice(
        invoice_number="INV1001",
        quantity=4,
        amount=200000,
    )

    assert response1.status_code == 201, response1.text

    data1 = response1.json()

    assert data1["invoice_number"] == "INV1001"
    assert data1["amount"] == 200000

    # Invoice creation moves the P2P state from received
    # to invoiced. Restore it for the second invoice.
    p2p_states["PO1001"] = P2PState.received

    # --------------------------------------------------------
    # Second partial invoice: 6 / 10
    # --------------------------------------------------------

    response2 = create_sample_invoice(
        invoice_number="INV1002",
        quantity=6,
        amount=300000,
    )

    assert response2.status_code == 201, response2.text

    data2 = response2.json()

    assert data2["invoice_number"] == "INV1002"
    assert data2["amount"] == 300000

    # Both invoices belong to the same supplier.
    assert invoices[
        ("SUP001", "INV1001")
    ]["supplier_id"] == "SUP001"

    assert invoices[
        ("SUP001", "INV1002")
    ]["supplier_id"] == "SUP001"


# ============================================================
# INVOICE CREATION DOES NOT UPLOAD A DOCUMENT
# ============================================================

def test_invoice_creation_does_not_call_minio():
    create_received_po()

    authenticate_as(SUPPLIER_1_USER)

    with patch.object(
        invoice_service.document_storage_service,
        "upload_invoice_document",
    ) as mock_upload:

        response = create_sample_invoice(
            invoice_number="INV1101",
        )

    assert response.status_code == 201, response.text

    mock_upload.assert_not_called()

    assert invoices[
        ("SUP001", "INV1101")
    ]["document_path"] is None

    assert invoices[
        ("SUP001", "INV1101")
    ]["document_url"] is None


# ============================================================
# INVOICE DOCUMENT UPLOAD IS A SEPARATE OPERATION
# ============================================================

def test_invoice_can_be_created_then_document_uploaded():
    create_received_po()

    authenticate_as(SUPPLIER_1_USER)

    # Step 1: create invoice.
    response = create_sample_invoice(
        invoice_number="INV1201",
    )

    assert response.status_code == 201, response.text

    invoice = invoices[
        ("SUP001", "INV1201")
    ]

    assert invoice["document_path"] is None

    # Step 2: upload document separately.
    expected_key = (
        "suppliers/SUP001/invoices/INV1201.pdf"
    )

    with patch.object(
        invoice_service.document_storage_service,
        "upload_invoice_document",
        return_value=expected_key,
    ) as mock_upload:

        response = client.post(
            "/api/v1/invoices/"
            "SUP001/INV1201/document",
            files={
                "file": (
                    "invoice.pdf",
                    valid_pdf(),
                    "application/pdf",
                )
            },
        )

    assert response.status_code == 200, response.text

    invoice = invoices[
        ("SUP001", "INV1201")
    ]

    assert invoice["document_path"] == expected_key

    assert invoice["document_url"] == (
        "/api/v1/invoices/SUP001/INV1201/document"
    )

    mock_upload.assert_called_once()


# ============================================================
# OVER-INVOICING AFTER PARTIAL INVOICE
# ============================================================

def test_over_invoice_after_partial_invoice():
    create_received_po(quantity=10)

    authenticate_as(SUPPLIER_1_USER)

    # First invoice consumes 7 units.
    response1 = create_sample_invoice(
        invoice_number="INV1001",
        quantity=7,
        amount=350000,
    )

    assert response1.status_code == 201, response1.text

    # First invoice moves P2P to invoiced.
    # Reset to received so the second invoice can be
    # validated against the remaining PO quantity.
    p2p_states["PO1001"] = P2PState.received

    # Only 3 units remain.
    # Requesting 4 must fail.
    response2 = create_sample_invoice(
        invoice_number="INV1002",
        quantity=4,
        amount=200000,
    )

    assert response2.status_code == 400, response2.text

    assert "cannot exceed" in (
        response2.json()["detail"].lower()
    )

    # Failed invoice must not be persisted.
    assert ("SUP001", "INV1002") not in invoices


# ============================================================
# UNIT PRICE ABOVE TOLERANCE
# ============================================================

def test_invoice_unit_price_above_tolerance():
    create_received_po(
        unit_price=50000,
    )

    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV1001",
        unit_price=53000,
        amount=53000,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["invoice_number"] == "INV1001"
    assert data["supplier_id"] == "SUP001"
    assert data["items"][0]["unit_price"] == 53000


# ============================================================
# UNIT PRICE BELOW TOLERANCE
# ============================================================

def test_invoice_unit_price_below_tolerance():
    create_received_po(
        unit_price=50000,
    )

    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV1002",
        unit_price=46000,
        amount=46000,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["invoice_number"] == "INV1002"
    assert data["supplier_id"] == "SUP001"
    assert data["items"][0]["unit_price"] == 46000


# ============================================================
# AMOUNT TOO HIGH
# ============================================================

def test_invoice_amount_too_high():
    create_received_po()

    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV3001",
        amount=70000,
    )

    assert response.status_code == 400, response.text

    assert "invoice amount" in (
        response.json()["detail"].lower()
    )

    assert ("SUP001", "INV3001") not in invoices


# ============================================================
# AMOUNT TOO LOW
# ============================================================

def test_invoice_amount_too_low():
    create_received_po()

    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV3002",
        amount=30000,
    )

    assert response.status_code == 400, response.text

    assert "invoice amount" in (
        response.json()["detail"].lower()
    )

    assert ("SUP001", "INV3002") not in invoices


# ============================================================
# DUPLICATE PO / ITEM LINE INSIDE SAME INVOICE
# ============================================================

def test_duplicate_invoice_line():
    create_received_po()

    authenticate_as(SUPPLIER_1_USER)

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

    assert response.status_code == 400, response.text

    assert "duplicate invoice line" in (
        response.json()["detail"].lower()
    )

    assert ("SUP001", "INV5001") not in invoices


# ============================================================
# EMPTY ITEMS
# ============================================================

def test_invoice_empty_items():
    authenticate_as(SUPPLIER_1_USER)

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

    # Pydantic min_length=1 validation.
    assert response.status_code == 422, response.text


# ============================================================
# INVALID INVOICE NUMBER
# ============================================================

def test_invalid_invoice_number():
    create_received_po()

    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV@1001",
    )

    # Pydantic catches the invalid format before
    # invoice business logic or MinIO is reached.
    assert response.status_code == 422, response.text


# ============================================================
# INVALID SUPPLIER ID
# ============================================================

def test_invalid_supplier_id():
    create_received_po()

    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV1001",
        supplier_id="../uploads_evil",
    )

    # Invalid supplier ID is rejected by schema validation.
    # No MinIO upload should occur because this is only
    # invoice creation.
    assert response.status_code == 422, response.text


# ============================================================
# INVALID PO NUMBER FORMAT
# ============================================================

def test_invalid_po_number_format():
    authenticate_as(SUPPLIER_1_USER)

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

    assert response.status_code == 422, response.text


# ============================================================
# INVALID ITEM CODE FORMAT
# ============================================================

def test_invalid_item_code_format():
    authenticate_as(SUPPLIER_1_USER)

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

    assert response.status_code == 422, response.text


# ============================================================
# INVALID QUANTITY - ZERO
# ============================================================

def test_invoice_quantity_zero():
    authenticate_as(SUPPLIER_1_USER)

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

    assert response.status_code == 422, response.text


# ============================================================
# INVALID UNIT PRICE - ZERO
# ============================================================

def test_invoice_unit_price_zero():
    authenticate_as(SUPPLIER_1_USER)

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

    assert response.status_code == 422, response.text
  # ============================================================
# INVALID AMOUNT - ZERO
# ============================================================

def test_invoice_amount_zero():
    authenticate_as(SUPPLIER_1_USER)

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

    assert response.status_code == 422, response.text


# ============================================================
# INVALID DATE
# ============================================================

def test_invalid_invoice_date():
    authenticate_as(SUPPLIER_1_USER)

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

    assert response.status_code == 422, response.text


# ============================================================
# MISSING REQUIRED FIELD
# ============================================================

def test_invoice_missing_supplier_id():
    authenticate_as(SUPPLIER_1_USER)

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

    assert response.status_code == 422, response.text


# ============================================================
# SUPPLIER DOES NOT MATCH PO
# ============================================================

def test_invoice_supplier_does_not_match_po():
    # PO belongs to SUP001.
    create_received_po(
        po_number="PO1001",
        supplier_id="SUP001",
    )

    # Authenticate as a different supplier.
    authenticate_as(SUPPLIER_2_USER)

    response = create_sample_invoice(
        invoice_number="INV1001",
        po_number="PO1001",
        supplier_id="SUP002",
    )

    # Supplier scoping must reject the request before
    # invoice business logic or MinIO is reached.
    assert response.status_code == 403, response.text

    assert "supplier" in (
        response.json()["detail"].lower()
    )

    assert ("SUP002", "INV1001") not in invoices


# ============================================================
# UPLOAD VALID PDF TO MINIO
# ============================================================

def test_upload_invoice_pdf():
    create_received_po()

    response = create_sample_invoice(
        invoice_number="INV1001",
    )

    assert response.status_code == 201, response.text

    authenticate_as(SUPPLIER_1_USER)

    expected_key = (
        "suppliers/SUP001/invoices/INV1001.pdf"
    )

    # Unit test: mock MinIO upload.
    # Actual MinIO behavior is covered by integration tests.
    with patch.object(
        invoice_service.document_storage_service,
        "upload_invoice_document",
        return_value=expected_key,
    ) as mock_upload:

        response = client.post(
            "/api/v1/invoices/SUP001/INV1001/document",
            files={
                "file": (
                    "invoice.pdf",
                    valid_pdf_bytes(),
                    "application/pdf",
                )
            },
        )

    assert response.status_code == 200, response.text

    body = response.json()

    # --------------------------------------------------------
    # Public response
    # --------------------------------------------------------

    assert body["invoice_number"] == "INV1001"

    assert body["document_url"] == (
        "/api/v1/invoices/SUP001/INV1001/document"
    )

    # Internal MinIO object key must NOT be exposed.
    assert "document_path" not in body

    # --------------------------------------------------------
    # Internal storage metadata
    # --------------------------------------------------------

    invoice_key = ("SUP001", "INV1001")

    assert invoices[invoice_key]["document_path"] == (
        "suppliers/SUP001/invoices/INV1001.pdf"
    )

    assert invoices[invoice_key]["document_url"] == (
        "/api/v1/invoices/SUP001/INV1001/document"
    )

    mock_upload.assert_called_once()

    call_kwargs = mock_upload.call_args.kwargs

    assert call_kwargs["supplier_id"] == "SUP001"
    assert call_kwargs["invoice_number"] == "INV1001"


# ============================================================
# VERIFY SUPPLIER-SCOPED MINIO OBJECT KEY
# ============================================================

def test_invoice_document_saved_under_supplier_scoped_minio_key():
    create_received_po()

    response = create_sample_invoice(
        invoice_number="INV9101",
    )

    assert response.status_code == 201, response.text

    authenticate_as(SUPPLIER_1_USER)

    expected_key = (
        "suppliers/SUP001/invoices/INV9101.pdf"
    )

    with patch.object(
        invoice_service.document_storage_service,
        "upload_invoice_document",
        return_value=expected_key,
    ) as mock_upload:

        response = client.post(
            "/api/v1/invoices/SUP001/INV9101/document",
            files={
                "file": (
                    "invoice.pdf",
                    valid_pdf_bytes(),
                    "application/pdf",
                )
            },
        )

    assert response.status_code == 200, response.text

    assert invoices[
        ("SUP001", "INV9101")
    ]["document_path"] == (
        "suppliers/SUP001/invoices/INV9101.pdf"
    )

    mock_upload.assert_called_once()


# ============================================================
# UPLOAD DOCUMENT FOR NON-EXISTING INVOICE
# ============================================================

def test_upload_document_invoice_not_found():
    authenticate_as(SUPPLIER_1_USER)

    with patch.object(
        invoice_service.document_storage_service,
        "upload_invoice_document",
    ) as mock_upload:

        response = client.post(
            "/api/v1/invoices/SUP001/INV9999/document",
            files={
                "file": (
                    "invoice.pdf",
                    valid_pdf_bytes(),
                    "application/pdf",
                )
            },
        )

    assert response.status_code == 404, response.text

    assert response.json()["detail"] == (
        "Invoice not found."
    )

    # Important: MinIO must never be called when the
    # invoice itself does not exist.
    mock_upload.assert_not_called()


# ============================================================
# INVOICE QUANTITY EXACTLY MATCHES PO QUANTITY
# ============================================================

def test_invoice_quantity_exactly_matches_po_quantity():
    create_received_po(
        quantity=10,
        unit_price=50000,
    )

    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV1001",
        quantity=10,
        amount=500000,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["invoice_number"] == "INV1001"
    assert data["supplier_id"] == "SUP001"
    assert data["amount"] == 500000


# ============================================================
# INVOICE REJECTED AFTER PO FULLY INVOICED
# ============================================================

def test_invoice_rejected_after_po_fully_invoiced():
    create_received_po(
        quantity=10,
    )

    authenticate_as(SUPPLIER_1_USER)

    # First invoice consumes all 10 units.
    response = create_sample_invoice(
        invoice_number="INV1001",
        quantity=10,
        amount=500000,
    )

    assert response.status_code == 201, response.text

    # The first invoice moves P2P:
    #
    # received -> invoiced
    #
    # Reset only the workflow state so that the second
    # invoice reaches quantity reconciliation.
    p2p_states["PO1001"] = P2PState.received

    response = create_sample_invoice(
        invoice_number="INV1002",
        quantity=1,
        amount=50000,
    )

    assert response.status_code == 400, response.text

    assert "cannot exceed" in (
        response.json()["detail"].lower()
    )

    # Failed invoice must not be persisted.
    assert ("SUP001", "INV1002") not in invoices


# ============================================================
# DOCUMENT NOT FOUND
# ============================================================

def test_document_not_found():
    create_received_po()

    response = create_sample_invoice(
        invoice_number="INV1001",
    )

    assert response.status_code == 201, response.text

    authenticate_as(SUPPLIER_1_USER)

    # Invoice exists, but no document_path has been registered.
    assert invoices[
        ("SUP001", "INV1001")
    ]["document_path"] is None

    response = client.get(
        "/api/v1/invoices/SUP001/INV1001/document"
    )

    assert response.status_code == 404, response.text

    assert response.json()["detail"] == (
        "Document not found."
    )


# ============================================================
# INVOICE DOCUMENT NOT FOUND
# ============================================================

def test_invoice_document_invoice_not_found():
    authenticate_as(SUPPLIER_1_USER)

    response = client.get(
        "/api/v1/invoices/SUP001/INV9999/document"
    )

    assert response.status_code == 404, response.text

    assert response.json()["detail"] == (
        "Invoice not found."
    )


# ============================================================
# LARGE PDF
# ============================================================

def test_large_pdf_rejected():
    create_received_po()

    response = create_sample_invoice(
        invoice_number="INV1001",
    )

    assert response.status_code == 201, response.text

    authenticate_as(SUPPLIER_1_USER)

    large_pdf = (
        b"%PDF-1.4\n"
        + b"a" * (
            11 * 1024 * 1024
        )
    )

    with patch.object(
        invoice_service.document_storage_service,
        "upload_invoice_document",
    ) as mock_upload:

        response = client.post(
            "/api/v1/invoices/SUP001/INV1001/document",
            files={
                "file": (
                    "large.pdf",
                    BytesIO(large_pdf),
                    "application/pdf",
                )
            },
        )

    assert response.status_code == 400, response.text

    assert response.json()["detail"] == (
        "Maximum file size is 10 MB."
    )

    # Validation must happen before MinIO upload.
    mock_upload.assert_not_called()


# ============================================================
# PDF EXACTLY 10 MB
# ============================================================

def test_pdf_exactly_10_mb_accepted():
    create_received_po()

    response = create_sample_invoice(
        invoice_number="INV9501",
    )

    assert response.status_code == 201, response.text

    authenticate_as(SUPPLIER_1_USER)

    pdf_header = b"%PDF-1.4\n"

    pdf_content = (
        pdf_header
        + b"a" * (
            10 * 1024 * 1024
            - len(pdf_header)
        )
    )

    expected_key = (
        "suppliers/SUP001/invoices/INV9501.pdf"
    )

    with patch.object(
        invoice_service.document_storage_service,
        "upload_invoice_document",
        return_value=expected_key,
    ) as mock_upload:

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

    assert response.status_code == 200, response.text

    assert invoices[
        ("SUP001", "INV9501")
    ]["document_path"] == expected_key

    mock_upload.assert_called_once()


# ============================================================
# DOWNLOAD INVOICE DOCUMENT
# ============================================================

def test_download_invoice_document():
    create_submitted_invoice()

    expected_key = (
        "suppliers/SUP001/invoices/INV1001.pdf"
    )

    invoices[
        ("SUP001", "INV1001")
    ]["document_path"] = expected_key

    authenticate_as(SUPPLIER_1_USER)

    with patch.object(
        invoice_service.document_storage_service,
        "generate_download_url",
        return_value="http://minio/presigned-url",
    ) as mock_generate_url:

        response = client.get(
            "/api/v1/invoices/"
            "SUP001/INV1001/document"
        )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["invoice_number"] == "INV1001"
    assert data["supplier_id"] == "SUP001"
    assert data["file_name"] == "INV1001.pdf"
    assert data["download_url"] == (
        "http://minio/presigned-url"
    )
    assert data["expires_in_seconds"] > 0

    mock_generate_url.assert_called_once_with(
        object_key=expected_key,
    )
# ============================================================
# FILE DOES NOT EXIST AFTER UPLOAD
# ============================================================

def test_file_deleted_after_upload():
    create_received_po()

    response = create_sample_invoice(
        invoice_number="INV1001",
    )

    assert response.status_code == 201, response.text

    authenticate_as(SUPPLIER_1_USER)

    expected_key = (
        "suppliers/SUP001/invoices/INV1001.pdf"
    )

    # Upload the document to MinIO.
    with patch.object(
        invoice_service.document_storage_service,
        "upload_invoice_document",
        return_value=expected_key,
    ) as mock_upload:

        upload_response = client.post(
            "/api/v1/invoices/SUP001/INV1001/document",
            files={
                "file": (
                    "invoice.pdf",
                    valid_pdf_bytes(),
                    "application/pdf",
                )
            },
        )

    assert upload_response.status_code == 200, (
        upload_response.text
    )

    mock_upload.assert_called_once()

    invoice_key = ("SUP001", "INV1001")

    assert invoices[invoice_key]["document_path"] == (
        "suppliers/SUP001/invoices/INV1001.pdf"
    )

    # --------------------------------------------------------
    # Simulate the MinIO object being deleted externally.
    #
    # The invoice metadata still contains the object key,
    # but the actual object no longer exists.
    # --------------------------------------------------------

    with patch.object(
        invoice_service.document_storage_service,
        "object_exists",
        return_value=False,
    ) as mock_exists:

        response = client.get(
            "/api/v1/invoices/SUP001/INV1001/document"
        )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # This assertion depends on the production download route
    # checking MinIO object existence before generating the
    # presigned URL.
    # --------------------------------------------------------

    assert response.status_code == 404, response.text

    assert response.json()["detail"] == (
        "File does not exist."
    )

    mock_exists.assert_called_once_with(
        object_key=expected_key,
    )


# ============================================================
# DOCUMENT URL STORED
# ============================================================

def test_document_url_saved_in_memory():
    create_received_po()

    response = create_sample_invoice(
        invoice_number="INV1001",
    )

    assert response.status_code == 201, response.text

    invoice_key = ("SUP001", "INV1001")

    # Before upload there is no document.
    assert invoices[invoice_key]["document_url"] is None
    assert invoices[invoice_key]["document_path"] is None

    authenticate_as(SUPPLIER_1_USER)

    expected_key = (
        "suppliers/SUP001/invoices/INV1001.pdf"
    )

    with patch.object(
        invoice_service.document_storage_service,
        "upload_invoice_document",
        return_value=expected_key,
    ) as mock_upload:

        upload_response = client.post(
            "/api/v1/invoices/SUP001/INV1001/document",
            files={
                "file": (
                    "invoice.pdf",
                    valid_pdf_bytes(),
                    "application/pdf",
                )
            },
        )

    assert upload_response.status_code == 200, (
        upload_response.text
    )

    # Public API URL remains stable.
    assert invoices[invoice_key]["document_url"] == (
        "/api/v1/invoices/SUP001/INV1001/document"
    )

    # Internal value is now the MinIO object key.
    assert invoices[invoice_key]["document_path"] == (
        "suppliers/SUP001/invoices/INV1001.pdf"
    )

    mock_upload.assert_called_once()


# ============================================================
# SUPPLIER-SCOPED MINIO OBJECT KEY
# ============================================================

def test_invoice_document_saved_under_supplier_directory():
    # --------------------------------------------------------
    # Create PO belonging to SUP123.
    # --------------------------------------------------------

    create_received_po(
        supplier_id="SUP123",
    )

    # --------------------------------------------------------
    # Create invoice belonging to SUP123.
    # --------------------------------------------------------

    authenticate_as(SUPPLIER_123_USER)

    response = create_sample_invoice(
        invoice_number="INV1001",
        supplier_id="SUP123",
    )

    assert response.status_code == 201, response.text

    # --------------------------------------------------------
    # Upload document.
    # --------------------------------------------------------

    expected_key = (
        "suppliers/SUP123/invoices/INV1001.pdf"
    )

    with patch.object(
        invoice_service.document_storage_service,
        "upload_invoice_document",
        return_value=expected_key,
    ) as mock_upload:

        upload_response = client.post(
            "/api/v1/invoices/SUP123/INV1001/document",
            files={
                "file": (
                    "invoice.pdf",
                    valid_pdf_bytes(),
                    "application/pdf",
                )
            },
        )

    assert upload_response.status_code == 200, (
        upload_response.text
    )

    invoice_key = ("SUP123", "INV1001")

    # --------------------------------------------------------
    # Internal MinIO object key.
    # --------------------------------------------------------

    document_path = invoices[invoice_key]["document_path"]

    assert document_path == (
        "suppliers/SUP123/invoices/INV1001.pdf"
    )

    mock_upload.assert_called_once()

    # --------------------------------------------------------
    # Public API URL.
    # --------------------------------------------------------

    body = upload_response.json()

    assert body["document_url"] == (
        "/api/v1/invoices/SUP123/INV1001/document"
    )

    # Internal MinIO key must never be exposed.
    assert "document_path" not in body


# ============================================================
# INVOICE CREATE DOES NOT CREATE DOCUMENT
# ============================================================

def test_invoice_document_url_initially_none():
    create_received_po()

    response = create_sample_invoice(
        invoice_number="INV1001",
    )

    assert response.status_code == 201, response.text

    # --------------------------------------------------------
    # Public API response.
    # --------------------------------------------------------

    data = response.json()

    assert data["document_url"] is None

    # Internal storage key must never be exposed.
    assert "document_path" not in data

    # --------------------------------------------------------
    # Internal invoice storage.
    # --------------------------------------------------------

    invoice_key = ("SUP001", "INV1001")

    assert invoices[invoice_key]["document_path"] is None
    assert invoices[invoice_key]["document_url"] is None


# ============================================================
# GET AFTER UPLOAD
# ============================================================

def test_get_invoice_after_document_upload():
    create_received_po()

    response = create_sample_invoice(
        invoice_number="INV1001",
    )

    assert response.status_code == 201, response.text

    authenticate_as(SUPPLIER_1_USER)

    expected_key = (
        "suppliers/SUP001/invoices/INV1001.pdf"
    )

    with patch.object(
        invoice_service.document_storage_service,
        "upload_invoice_document",
        return_value=expected_key,
    ) as mock_upload:

        upload_response = client.post(
            "/api/v1/invoices/SUP001/INV1001/document",
            files={
                "file": (
                    "invoice.pdf",
                    valid_pdf_bytes(),
                    "application/pdf",
                )
            },
        )

    assert upload_response.status_code == 200, (
        upload_response.text
    )

    mock_upload.assert_called_once()

    response = client.get(
        "/api/v1/invoices/SUP001/INV1001"
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["invoice_number"] == "INV1001"

    assert data["document_url"] is not None

    assert data["document_url"] == (
        "/api/v1/invoices/SUP001/INV1001/document"
    )

    # Internal MinIO key must not be exposed.
    assert "document_path" not in data


# ============================================================
# MULTI-PO INVOICE
# ============================================================

def test_invoice_with_multiple_purchase_orders():
    # --------------------------------------------------------
    # PO 1
    # --------------------------------------------------------

    create_received_po(
        po_number="PO1001",
        supplier_id="SUP001",
        item_code="LAPTOP",
        quantity=5,
        unit_price=50000,
    )

    # --------------------------------------------------------
    # PO 2
    # --------------------------------------------------------

    create_received_po(
        po_number="PO1002",
        supplier_id="SUP001",
        item_code="MOUSE",
        quantity=10,
        unit_price=1500,
    )

    authenticate_as(SUPPLIER_1_USER)

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

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["invoice_number"] == "INV7001"
    assert data["supplier_id"] == "SUP001"
    assert len(data["items"]) == 2
    assert data["amount"] == 107500

    # Creating an invoice does not upload a document.
    assert invoices[
        ("SUP001", "INV7001")
    ]["document_path"] is None


# ============================================================
# MULTIPLE ITEMS SAME PO
# ============================================================

def test_invoice_multiple_items_same_po():
    # --------------------------------------------------------
    # Create PO.
    # --------------------------------------------------------

    create_sample_po(
        po_number="PO1001",
        item_code="LAPTOP",
        quantity=5,
        unit_price=50000,
    )

    # Add second item to the PO.
    purchase_orders["PO1001"]["items"].append(
        {
            "item_code": "MOUSE",
            "description": "Mouse",
            "quantity": 10,
            "unit_price": 1500,
        }
    )

    # Move PO to acknowledged.
    acknowledge_po("PO1001")

    # Prepare P2P state for invoice creation.
    p2p_states["PO1001"] = P2PState.received

    authenticate_as(SUPPLIER_1_USER)

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

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["invoice_number"] == "INV8001"
    assert data["supplier_id"] == "SUP001"
    assert len(data["items"]) == 2
    assert data["amount"] == 53000

    # No document is created during invoice creation.
    assert invoices[
        ("SUP001", "INV8001")
    ]["document_path"] is None
# ============================================================
# ORPHANED INVOICE FILE TEST SETUP - MINIO
# ============================================================

@pytest.fixture
def orphan_test_setup():
    """
    Create isolated MinIO object metadata for orphan-file tests.

    The production orphan scanner reads objects from MinIO,
    so these tests mock list_objects() instead of creating
    files on the local filesystem.
    """

    invoice_service.invoices.clear()
    invoice_service.invoice_events.clear()

    objects = []

    with patch.object(
        invoice_service.document_storage_service,
        "list_objects",
        return_value=objects,
    ) as mock_list_objects:

        yield objects, mock_list_objects

    invoice_service.invoices.clear()
    invoice_service.invoice_events.clear()


def add_minio_invoice_object(
    objects,
    supplier_id: str,
    invoice_number: str,
    *,
    age_days: int = 2,
    size: int = 100,
):
    """
    Add a fake MinIO object to the mocked list_objects()
    result.

    The object follows the production MinIO key structure:
        suppliers/{supplier_id}/invoices/{invoice_number}.pdf
    """

    object_key = (
        f"suppliers/{supplier_id}/"
        f"invoices/{invoice_number}.pdf"
    )

    objects.append(
        SimpleNamespace(
            object_name=object_key,
            last_modified=(
                datetime.now(timezone.utc)
                - timedelta(days=age_days)
            ),
            size=size,
        )
    )

    return object_key


# ============================================================
# TEST 1 - NO MINIO OBJECTS
# ============================================================

def test_find_orphaned_files_when_no_minio_objects_exist(
    orphan_test_setup,
):
    """
    If MinIO has no invoice objects, no orphaned files
    should be returned.
    """

    objects, mock_list_objects = orphan_test_setup

    result = (
        invoice_service.find_orphaned_invoice_files(
            older_than_days=1,
        )
    )

    assert result == []

    mock_list_objects.assert_called_once_with(
        prefix="suppliers/",
    )


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
    An old MinIO PDF with no matching invoice record
    must be considered orphaned.
    """

    objects, _ = orphan_test_setup

    object_key = add_minio_invoice_object(
        objects=objects,
        supplier_id="SUP001",
        invoice_number="INV001",
        age_days=2,
        size=100,
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

    # MinIO object key, not an absolute filesystem path.
    assert orphan["file_path"] == object_key

    assert orphan["file_path"] == (
        "suppliers/SUP001/invoices/INV001.pdf"
    )

    assert orphan["size_bytes"] == 100
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
    Their MinIO files must not be considered orphaned.
    """

    objects, _ = orphan_test_setup

    object_key = add_minio_invoice_object(
        objects=objects,
        supplier_id="SUP001",
        invoice_number="INV002",
        age_days=2,
    )

    invoice_service.invoices[
        ("SUP001", "INV002")
    ] = {
        "invoice_number": "INV002",
        "supplier_id": "SUP001",
        "status": InvoiceStatus.approved,
        "document_url": (
            "/api/v1/invoices/"
            "SUP001/INV002/document"
        ),
        "document_path": object_key,
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
    Their MinIO files must not be considered orphaned.
    """

    objects, _ = orphan_test_setup

    object_key = add_minio_invoice_object(
        objects=objects,
        supplier_id="SUP001",
        invoice_number="INV003",
        age_days=2,
    )

    invoice_service.invoices[
        ("SUP001", "INV003")
    ] = {
        "invoice_number": "INV003",
        "supplier_id": "SUP001",
        "status": InvoiceStatus.rejected,
        "document_url": (
            "/api/v1/invoices/"
            "SUP001/INV003/document"
        ),
        "document_path": object_key,
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

    If its MinIO PDF is older than the configured threshold,
    it is considered orphaned by the current cleanup policy.
    """

    objects, _ = orphan_test_setup

    object_key = add_minio_invoice_object(
        objects=objects,
        supplier_id="SUP001",
        invoice_number="INV004",
        age_days=2,
    )

    invoice_service.invoices[
        ("SUP001", "INV004")
    ] = {
        "invoice_number": "INV004",
        "supplier_id": "SUP001",
        "status": InvoiceStatus.submitted,
        "document_path": object_key,
        "document_url": (
            "/api/v1/invoices/"
            "SUP001/INV004/document"
        ),
    }

    result = (
        invoice_service.find_orphaned_invoice_files(
            older_than_days=1,
        )
    )

    assert len(result) == 1

    orphan = result[0]

    assert orphan["invoice_number"] == "INV004"
    assert orphan["supplier_id"] == "SUP001"
    assert orphan["invoice_status"] == "submitted"

    assert orphan["file_path"] == (
        "suppliers/SUP001/invoices/INV004.pdf"
    )

    assert (
        "not in a terminal state"
        in orphan["reason"]
    )


# ============================================================
# TEST 7 - NON-TERMINAL FILE WITHOUT DOCUMENT PATH
# ============================================================

def test_non_terminal_invoice_without_document_path_is_orphaned(
    orphan_test_setup,
):
    """
    If the invoice exists but document_path is missing,
    the old MinIO PDF has no registered association.
    """

    objects, _ = orphan_test_setup

    object_key = add_minio_invoice_object(
        objects=objects,
        supplier_id="SUP002",
        invoice_number="INV005",
        age_days=2,
    )

    invoice_service.invoices[
        ("SUP002", "INV005")
    ] = {
        "invoice_number": "INV005",
        "supplier_id": "SUP002",
        "status": InvoiceStatus.disputed,
        "document_path": None,
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
    assert orphan["supplier_id"] == "SUP002"
    assert orphan["invoice_status"] == "disputed"

    assert orphan["file_path"] == object_key

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
    If invoice.document_path points to another MinIO object,
    the discovered object is orphaned.
    """

    objects, _ = orphan_test_setup

    actual_object_key = add_minio_invoice_object(
        objects=objects,
        supplier_id="SUP003",
        invoice_number="INV006",
        age_days=2,
    )

    wrong_document_path = (
        "suppliers/SUP003/"
        "invoices/different-file.pdf"
    )

    invoice_service.invoices[
        ("SUP003", "INV006")
    ] = {
        "invoice_number": "INV006",
        "supplier_id": "SUP003",
        "status": InvoiceStatus.submitted,
        "document_path": wrong_document_path,
        "document_url": (
            "/api/v1/invoices/"
            "SUP003/INV006/document"
        ),
    }

    result = (
        invoice_service.find_orphaned_invoice_files(
            older_than_days=1,
        )
    )

    assert len(result) == 1

    orphan = result[0]

    assert orphan["invoice_number"] == "INV006"
    assert orphan["supplier_id"] == "SUP003"

    assert orphan["file_path"] == actual_object_key

    assert orphan["file_path"] == (
        "suppliers/SUP003/invoices/INV006.pdf"
    )

    assert (
        "file object key does not match"
        in orphan["reason"].lower()
    )


# ============================================================
# TEST 9 - RECENT FILE IS NOT ORPHANED
# ============================================================

def test_recent_invoice_file_is_not_orphaned(
    orphan_test_setup,
):
    """
    Files newer than older_than_days must be ignored.
    """

    objects, _ = orphan_test_setup

    object_key = add_minio_invoice_object(
        objects=objects,
        supplier_id="SUP004",
        invoice_number="INV007",
        age_days=0,
    )

    result = (
        invoice_service.find_orphaned_invoice_files(
            older_than_days=1,
        )
    )

    assert result == []

    # Object still exists in the mocked MinIO listing.
    assert any(
        obj.object_name == object_key
        for obj in objects
    )
# ============================================================
# TEST 10 - PURGE ORPHANED FILE
# ============================================================

def test_purge_deletes_orphaned_file(
    orphan_test_setup,
):
    """
    purge_orphaned_invoice_files() must delete the
    orphaned MinIO object.
    """

    objects, mock_list_objects = orphan_test_setup

    object_key = add_minio_invoice_object(
        objects,
        supplier_id="SUP005",
        invoice_number="INV008",
        age_days=2,
    )

    with patch.object(
        invoice_service.document_storage_service,
        "delete_object",
    ) as mock_delete:

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

    assert (
        result["files"][0]["supplier_id"]
        == "SUP005"
    )

    assert (
        result["files"][0]["file_path"]
        == object_key
    )

    mock_list_objects.assert_called_once_with(
        prefix="suppliers/"
    )

    mock_delete.assert_called_once_with(
        object_key=object_key,
    )


# ============================================================
# TEST 11 - PURGE DOES NOT DELETE APPROVED FILE
# ============================================================

def test_purge_does_not_delete_approved_file(
    orphan_test_setup,
):
    """
    Approved invoice documents must remain untouched.
    """

    objects, mock_list_objects = orphan_test_setup

    object_key = add_minio_invoice_object(
        objects,
        supplier_id="SUP006",
        invoice_number="INV009",
        age_days=2,
    )

    invoice_service.invoices[
        ("SUP006", "INV009")
    ] = {
        "invoice_number": "INV009",
        "supplier_id": "SUP006",
        "status": InvoiceStatus.approved,
        "document_path": object_key,
        "document_url": (
            "/api/v1/invoices/"
            "SUP006/INV009/document"
        ),
    }

    with patch.object(
        invoice_service.document_storage_service,
        "delete_object",
    ) as mock_delete:

        result = (
            invoice_service.purge_orphaned_invoice_files(
                older_than_days=1,
            )
        )

    assert result["total"] == 0
    assert result["deleted"] == 0
    assert result["files"] == []

    mock_list_objects.assert_called_once_with(
        prefix="suppliers/"
    )

    mock_delete.assert_not_called()


# ============================================================
# TEST 12 - PURGE DOES NOT DELETE RECENT ORPHAN
# ============================================================

def test_purge_does_not_delete_recent_file(
    orphan_test_setup,
):
    """
    A recent MinIO object must not be deleted even if
    there is no invoice record.
    """

    objects, mock_list_objects = orphan_test_setup

    object_key = add_minio_invoice_object(
        objects,
        supplier_id="SUP007",
        invoice_number="INV010",
        age_days=0,
    )

    with patch.object(
        invoice_service.document_storage_service,
        "delete_object",
    ) as mock_delete:

        result = (
            invoice_service.purge_orphaned_invoice_files(
                older_than_days=1,
            )
        )

    assert result["total"] == 0
    assert result["deleted"] == 0
    assert result["files"] == []

    mock_list_objects.assert_called_once_with(
        prefix="suppliers/"
    )

    mock_delete.assert_not_called()


# ============================================================
# TEST 13 - PURGE MULTIPLE ORPHANED FILES
# ============================================================

def test_purge_multiple_orphaned_files(
    orphan_test_setup,
):
    """
    Multiple old orphaned MinIO objects should all be deleted.
    """

    objects, mock_list_objects = orphan_test_setup

    file1 = add_minio_invoice_object(
        objects,
        supplier_id="SUP008",
        invoice_number="INV011",
        age_days=3,
    )

    file2 = add_minio_invoice_object(
        objects,
        supplier_id="SUP008",
        invoice_number="INV012",
        age_days=3,
    )

    file3 = add_minio_invoice_object(
        objects,
        supplier_id="SUP009",
        invoice_number="INV013",
        age_days=3,
    )

    with patch.object(
        invoice_service.document_storage_service,
        "delete_object",
    ) as mock_delete:

        result = (
            invoice_service.purge_orphaned_invoice_files(
                older_than_days=1,
            )
        )

    assert result["total"] == 3
    assert result["deleted"] == 3

    assert len(result["files"]) == 3

    deleted_keys = {
        call.kwargs["object_key"]
        for call in mock_delete.call_args_list
    }

    assert deleted_keys == {
        file1,
        file2,
        file3,
    }

    assert mock_delete.call_count == 3

    mock_list_objects.assert_called_once_with(
        prefix="suppliers/"
    )


# ============================================================
# TEST 14 - PURGE MIXED FILES
# ============================================================

def test_purge_only_deletes_orphaned_files(
    orphan_test_setup,
):
    """
    Verify that purge deletes only orphaned MinIO objects.

    Old orphan       -> DELETE
    Old approved     -> KEEP
    Recent orphan    -> KEEP
    """

    objects, mock_list_objects = orphan_test_setup

    # --------------------------------------------------------
    # Old orphan
    # --------------------------------------------------------

    orphan_file = add_minio_invoice_object(
        objects,
        supplier_id="SUP010",
        invoice_number="INV014",
        age_days=3,
    )

    # --------------------------------------------------------
    # Old approved invoice
    # --------------------------------------------------------

    approved_file = add_minio_invoice_object(
        objects,
        supplier_id="SUP010",
        invoice_number="INV015",
        age_days=3,
    )

    invoice_service.invoices[
        ("SUP010", "INV015")
    ] = {
        "invoice_number": "INV015",
        "supplier_id": "SUP010",
        "status": InvoiceStatus.approved,
        "document_path": approved_file,
        "document_url": (
            "/api/v1/invoices/"
            "SUP010/INV015/document"
        ),
    }

    # --------------------------------------------------------
    # Recent orphan
    # --------------------------------------------------------

    recent_file = add_minio_invoice_object(
        objects,
        supplier_id="SUP010",
        invoice_number="INV016",
        age_days=0,
    )

    # --------------------------------------------------------
    # Execute purge
    # --------------------------------------------------------

    with patch.object(
        invoice_service.document_storage_service,
        "delete_object",
    ) as mock_delete:

        result = (
            invoice_service.purge_orphaned_invoice_files(
                older_than_days=1,
            )
        )

    # Only old orphan should be deleted.
    assert result["total"] == 1
    assert result["deleted"] == 1

    assert len(result["files"]) == 1

    assert (
        result["files"][0]["invoice_number"]
        == "INV014"
    )

    assert (
        result["files"][0]["file_path"]
        == orphan_file
    )

    # Only orphan object is deleted.
    mock_delete.assert_called_once_with(
        object_key=orphan_file,
    )

    # Approved and recent objects were not deleted.
    deleted_keys = {
        call.kwargs["object_key"]
        for call in mock_delete.call_args_list
    }

    assert approved_file not in deleted_keys
    assert recent_file not in deleted_keys


# ============================================================
# TEST 15 - PURGE DELETE FAILURE DOES NOT STOP OTHER FILES
# ============================================================

def test_purge_continues_when_one_minio_delete_fails(
    orphan_test_setup,
):
    """
    If deletion of one orphaned MinIO object fails,
    purge must continue attempting the remaining objects.
    """

    objects, mock_list_objects = orphan_test_setup

    file1 = add_minio_invoice_object(
        objects,
        supplier_id="SUP011",
        invoice_number="INV017",
        age_days=3,
    )

    file2 = add_minio_invoice_object(
        objects,
        supplier_id="SUP011",
        invoice_number="INV018",
        age_days=3,
    )

    file3 = add_minio_invoice_object(
        objects,
        supplier_id="SUP012",
        invoice_number="INV019",
        age_days=3,
    )

    def delete_side_effect(*, object_key):
        if object_key == file2:
            from app.services.document_storage_service import (
                DocumentStorageError,
            )

            raise DocumentStorageError(
                "Simulated MinIO deletion failure"
            )

    with patch.object(
        invoice_service.document_storage_service,
        "delete_object",
        side_effect=delete_side_effect,
    ) as mock_delete:

        result = (
            invoice_service.purge_orphaned_invoice_files(
                older_than_days=1,
            )
        )

    # All three were detected as orphaned.
    assert result["total"] == 3

    # Two were successfully deleted.
    assert result["deleted"] == 2

    deleted_invoice_numbers = {
        item["invoice_number"]
        for item in result["files"]
    }

    assert deleted_invoice_numbers == {
        "INV017",
        "INV019",
    }

    assert mock_delete.call_count == 3

    attempted_keys = {
        call.kwargs["object_key"]
        for call in mock_delete.call_args_list
    }

    assert attempted_keys == {
        file1,
        file2,
        file3,
    }


# ============================================================
# R5 - ORPHANED FILE AUTHORIZATION
# ============================================================

def test_supplier_cannot_scan_orphaned_invoice_files():
    """
    R5 Role Authorization:

    Orphaned-file scanning is a global maintenance operation.

    Suppliers must receive HTTP 403.
    """

    authenticate_as(SUPPLIER_1_USER)

    response = client.get(
        "/api/v1/maintenance/orphaned-invoice-files"
    )

    assert response.status_code == 403

    assert (
        response.json()["detail"]
        == (
            "Role 'supplier' is not authorized "
            "for this endpoint"
        )
    )


def test_supplier_cannot_purge_orphaned_invoice_files():
    """
    R5 Role Authorization:

    Purging orphaned files is destructive.

    Suppliers must receive HTTP 403.
    """

    authenticate_as(SUPPLIER_1_USER)

    response = client.delete(
        "/api/v1/maintenance/orphaned-invoice-files"
    )

    assert response.status_code == 403

    assert (
        response.json()["detail"]
        == (
            "Role 'supplier' is not authorized "
            "for this endpoint"
        )
    )


def test_compliance_officer_can_scan_orphaned_invoice_files(
    orphan_test_setup,
):
    """
    R5 Role Authorization:

    compliance_officer is authorized to scan orphaned
    invoice files.
    """

    objects, mock_list_objects = orphan_test_setup

    object_key = add_minio_invoice_object(
        objects,
        supplier_id="SUP001",
        invoice_number="INV9901",
        age_days=2,
    )

    authenticate_as(COMPLIANCE_USER)

    response = client.get(
        "/api/v1/maintenance/orphaned-invoice-files",
        params={
            "older_than_days": 1,
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["total"] == 1
    assert len(data["orphaned_files"]) == 1

    orphan = data["orphaned_files"][0]

    assert orphan["supplier_id"] == "SUP001"
    assert orphan["invoice_number"] == "INV9901"
    assert orphan["file_name"] == "INV9901.pdf"

    assert orphan["file_path"] == object_key

    mock_list_objects.assert_called_once_with(
        prefix="suppliers/"
    )


def test_compliance_officer_can_purge_orphaned_invoice_files(
    orphan_test_setup,
):
    """
    R5 Role Authorization:

    compliance_officer is authorized to permanently
    purge orphaned invoice files.
    """

    objects, mock_list_objects = orphan_test_setup

    object_key = add_minio_invoice_object(
        objects,
        supplier_id="SUP001",
        invoice_number="INV9902",
        age_days=2,
    )

    authenticate_as(COMPLIANCE_USER)

    with patch.object(
        invoice_service.document_storage_service,
        "delete_object",
    ) as mock_delete:

        response = client.delete(
            "/api/v1/maintenance/orphaned-invoice-files",
            params={
                "older_than_days": 1,
            },
        )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["total"] == 1
    assert data["deleted"] == 1

    assert len(data["files"]) == 1

    assert (
        data["files"][0]["invoice_number"]
        == "INV9902"
    )

    assert (
        data["files"][0]["file_path"]
        == object_key
    )

    mock_delete.assert_called_once_with(
        object_key=object_key,
    )

    mock_list_objects.assert_called_once_with(
        prefix="suppliers/"
    )


def test_supplier_cannot_purge_orphaned_file_physically(
    orphan_test_setup,
):
    """
    Security regression test:

    A supplier must not be able to trigger physical deletion
    of orphaned MinIO objects.
    """

    objects, mock_list_objects = orphan_test_setup

    object_key = add_minio_invoice_object(
        objects,
        supplier_id="SUP002",
        invoice_number="INV9903",
        age_days=2,
    )

    authenticate_as(SUPPLIER_1_USER)

    with patch.object(
        invoice_service.document_storage_service,
        "delete_object",
    ) as mock_delete:

        response = client.delete(
            "/api/v1/maintenance/orphaned-invoice-files",
            params={
                "older_than_days": 1,
            },
        )

    assert response.status_code == 403

    # Most important security assertion:
    # MinIO delete must never be called.
    mock_delete.assert_not_called()

    # The storage scanner must also never run because
    # authorization is rejected before the service executes.
    mock_list_objects.assert_not_called()


def test_procurement_manager_cannot_purge_orphaned_invoice_files():
    """
    Only compliance_officer may perform destructive
    orphan-file maintenance.
    """

    authenticate_as(PROCUREMENT_USER)

    response = client.delete(
        "/api/v1/maintenance/orphaned-invoice-files"
    )

    assert response.status_code == 403

    assert (
        response.json()["detail"]
        == (
            "Role 'procurement_manager' is not authorized "
            "for this endpoint"
        )
    )


def test_procurement_manager_cannot_scan_orphaned_invoice_files():
    """
    Orphan-file scanning is restricted to compliance_officer.
    """

    authenticate_as(PROCUREMENT_USER)

    response = client.get(
        "/api/v1/maintenance/orphaned-invoice-files"
    )

    assert response.status_code == 403

    assert (
        response.json()["detail"]
        == (
            "Role 'procurement_manager' is not authorized "
            "for this endpoint"
        )
    )


# ============================================================
# R5 AUTHORIZATION / SUPPLIER SCOPING TESTS
# ============================================================

def test_supplier_can_access_own_invoice():
    """
    R5:

    Supplier SUP001 must be able to access its own invoice.
    """

    # --------------------------------------------------------
    # Create PO and invoice for SUP001.
    # --------------------------------------------------------

    create_received_po(
        po_number="PO2001",
        supplier_id="SUP001",
    )

    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV2001",
        po_number="PO2001",
        supplier_id="SUP001",
    )

    assert response.status_code == 201, response.text

    # --------------------------------------------------------
    # Supplier accesses its own invoice.
    # --------------------------------------------------------

    response = client.get(
        "/api/v1/invoices/SUP001/INV2001"
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["invoice_number"] == "INV2001"
    assert data["supplier_id"] == "SUP001"


def test_supplier_cannot_access_other_supplier_invoice():
    """
    R5 Supplier Scoping:

    Authenticated supplier = SUP001
    Requested invoice owner = SUP002

    SUP001 must not be able to view SUP002's invoice.
    """

    # --------------------------------------------------------
    # Create PO and invoice for SUP002.
    # --------------------------------------------------------

    create_received_po(
        po_number="PO2002",
        supplier_id="SUP002",
    )

    authenticate_as(SUPPLIER_2_USER)

    response = create_sample_invoice(
        invoice_number="INV2002",
        po_number="PO2002",
        supplier_id="SUP002",
    )

    assert response.status_code == 201, response.text

    # --------------------------------------------------------
    # Switch to SUP001.
    # --------------------------------------------------------

    authenticate_as(SUPPLIER_1_USER)

    response = client.get(
        "/api/v1/invoices/SUP002/INV2002"
    )

    assert response.status_code == 403, response.text

    assert (
        response.json()["detail"]
        == "Forbidden: supplier does not own this invoice"
    )


def test_supplier_cannot_transition_other_supplier_invoice():
    """
    R5 Supplier Scoping:

    SUP001 must not be able to transition
    an invoice owned by SUP002.
    """

    # --------------------------------------------------------
    # Create SUP002 invoice.
    # --------------------------------------------------------

    create_received_po(
        po_number="PO2003",
        supplier_id="SUP002",
    )

    authenticate_as(SUPPLIER_2_USER)

    response = create_sample_invoice(
        invoice_number="INV2003",
        po_number="PO2003",
        supplier_id="SUP002",
    )

    assert response.status_code == 201, response.text

    # --------------------------------------------------------
    # Switch to SUP001.
    # --------------------------------------------------------

    authenticate_as(SUPPLIER_1_USER)

    response = client.post(
        "/api/v1/invoices/SUP002/INV2003/transition",
        json={
            "target_state": "disputed",
            "actor_id": "USER001",
            "actor_name": "Supplier User",
            "role": "supplier",
            "reason": "Attempting unauthorized access.",
        },
    )

    assert response.status_code == 403, response.text

    assert (
        response.json()["detail"]
        == "Forbidden: supplier does not own this invoice"
    )


def test_supplier_cannot_upload_document_for_other_supplier_invoice():
    """
    R5 Supplier Scoping:

    SUP001 must not be able to upload a document
    to an invoice owned by SUP002.
    """

    # --------------------------------------------------------
    # Create SUP002 invoice.
    # --------------------------------------------------------

    create_received_po(
        po_number="PO2004",
        supplier_id="SUP002",
    )

    authenticate_as(SUPPLIER_2_USER)

    response = create_sample_invoice(
        invoice_number="INV2004",
        po_number="PO2004",
        supplier_id="SUP002",
    )

    assert response.status_code == 201, response.text

    # --------------------------------------------------------
    # Switch to SUP001.
    # --------------------------------------------------------

    authenticate_as(SUPPLIER_1_USER)

    response = client.post(
        "/api/v1/invoices/SUP002/INV2004/document",
        files={
            "file": (
                "invoice.pdf",
                valid_pdf_bytes(),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 403, response.text

    assert (
        response.json()["detail"]
        == "Forbidden: supplier does not own this invoice"
    )


def test_supplier_cannot_download_other_supplier_invoice_document():
    """
    R5 Supplier Scoping:

    SUP001 must not be able to download
    a document belonging to SUP002.
    """

    # --------------------------------------------------------
    # Create SUP002 invoice.
    # --------------------------------------------------------

    create_received_po(
        po_number="PO2005",
        supplier_id="SUP002",
    )

    authenticate_as(SUPPLIER_2_USER)

    response = create_sample_invoice(
        invoice_number="INV2005",
        po_number="PO2005",
        supplier_id="SUP002",
    )

    assert response.status_code == 201, response.text

    # --------------------------------------------------------
    # Upload document as SUP002.
    # --------------------------------------------------------

    response = client.post(
        "/api/v1/invoices/SUP002/INV2005/document",
        files={
            "file": (
                "invoice.pdf",
                valid_pdf_bytes(),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200, response.text

    # --------------------------------------------------------
    # Switch to SUP001.
    # --------------------------------------------------------

    authenticate_as(SUPPLIER_1_USER)

    response = client.get(
        "/api/v1/invoices/SUP002/INV2005/document"
    )

    assert response.status_code == 403, response.text

    assert (
        response.json()["detail"]
        == "Forbidden: supplier does not own this invoice"
    )


def test_supplier_cannot_create_invoice_for_other_supplier():
    """
    R5 Supplier Scoping:

    SUP001 token must not be able to create an invoice
    claiming supplier_id = SUP002.
    """

    # --------------------------------------------------------
    # Create a valid SUP002 PO.
    # --------------------------------------------------------

    create_received_po(
        po_number="PO2006",
        supplier_id="SUP002",
    )

    # --------------------------------------------------------
    # Switch to SUP001.
    # --------------------------------------------------------

    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV2006",
        po_number="PO2006",
        supplier_id="SUP002",
    )

    assert response.status_code == 403, response.text

    assert (
        response.json()["detail"]
        == "Forbidden: supplier does not own this invoice"
    )


def test_supplier_cannot_adjust_invoice():
    """
    R5 Role Authorization:

    Invoice adjustment is restricted to the
    compliance_officer role.

    A supplier token must receive HTTP 403.
    """

    # --------------------------------------------------------
    # Create invoice for SUP001.
    # --------------------------------------------------------

    create_received_po(
        po_number="PO2007",
        supplier_id="SUP001",
    )

    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV2007",
        po_number="PO2007",
        supplier_id="SUP001",
    )

    assert response.status_code == 201, response.text

    # --------------------------------------------------------
    # Supplier disputes invoice.
    # --------------------------------------------------------

    response = client.post(
        "/api/v1/invoices/SUP001/INV2007/transition",
        json={
            "target_state": "disputed",
            "actor_id": "USER001",
            "actor_name": "Supplier User",
            "role": "supplier",
            "reason": "Invoice needs correction.",
        },
    )

    assert response.status_code == 200, response.text

    # --------------------------------------------------------
    # Supplier attempts compliance-only adjustment.
    # --------------------------------------------------------

    response = client.post(
        "/api/v1/invoices/SUP001/INV2007/adjust",
        json={
            "actor_id": "USER001",
            "actor_name": "Supplier User",
            "role": "supplier",
            "reason": "Unauthorized adjustment attempt.",
            "items": [
                {
                    "po_number": "PO2007",
                    "item_code": "LAPTOP",
                    "description": "Laptop",
                    "quantity": 1,
                    "unit_price": 50000,
                }
            ],
        },
    )

    assert response.status_code == 403, response.text

    assert (
        response.json()["detail"]
        == "Role 'supplier' is not authorized for this endpoint"
    )


def test_compliance_officer_can_adjust_supplier_invoice():
    """
    R5 Role Authorization:

    Compliance officer must be allowed to adjust
    a supplier invoice after it is disputed.
    """

    # --------------------------------------------------------
    # Create invoice as SUP001.
    # --------------------------------------------------------

    create_received_po(
        po_number="PO2008",
        supplier_id="SUP001",
    )

    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV2008",
        po_number="PO2008",
        supplier_id="SUP001",
    )

    assert response.status_code == 201, response.text

    # --------------------------------------------------------
    # Supplier disputes invoice.
    # --------------------------------------------------------

    response = client.post(
        "/api/v1/invoices/SUP001/INV2008/transition",
        json={
            "target_state": "disputed",
            "actor_id": "USER001",
            "actor_name": "Supplier User",
            "role": "supplier",
            "reason": "Incorrect invoice quantity.",
        },
    )

    assert response.status_code == 200, response.text

    # --------------------------------------------------------
    # Compliance officer adjusts invoice.
    # --------------------------------------------------------

    authenticate_as(COMPLIANCE_USER)

    response = client.post(
        "/api/v1/invoices/SUP001/INV2008/adjust",
        json={
            "actor_id": "USER002",
            "actor_name": "Compliance Officer",
            "role": "compliance_officer",
            "reason": "Correcting invoice quantity.",
            "items": [
                {
                    "po_number": "PO2008",
                    "item_code": "LAPTOP",
                    "description": "Laptop",
                    "quantity": 1,
                    "unit_price": 50000,
                }
            ],
        },
    )

    assert response.status_code == 200, response.text

    assert response.json()["status"] == "adjusted"


# ============================================================
# R5 - GET ALL INVOICES SUPPLIER SCOPING
# ============================================================

def test_supplier_get_all_invoices_returns_only_own_invoices():
    """
    R5 Supplier Scoping:

    SUP001 must only receive invoices belonging to SUP001.

    Invoices belonging to other suppliers must not be exposed.
    """

    # --------------------------------------------------------
    # Create SUP001 invoice.
    # --------------------------------------------------------

    create_received_po(
        po_number="PO2101",
        supplier_id="SUP001",
    )

    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV2101",
        po_number="PO2101",
        supplier_id="SUP001",
    )

    assert response.status_code == 201, response.text

    # --------------------------------------------------------
    # Create SUP002 invoice.
    # --------------------------------------------------------

    create_received_po(
        po_number="PO2102",
        supplier_id="SUP002",
    )

    authenticate_as(SUPPLIER_2_USER)

    response = create_sample_invoice(
        invoice_number="INV2102",
        po_number="PO2102",
        supplier_id="SUP002",
    )

    assert response.status_code == 201, response.text

    # --------------------------------------------------------
    # Request list as SUP001.
    # --------------------------------------------------------

    authenticate_as(SUPPLIER_1_USER)

    response = client.get(
        "/api/v1/invoices"
    )

    assert response.status_code == 200, response.text

    data = response.json()

    # Only SUP001 invoice must be visible.
    assert len(data) == 1

    assert data[0]["invoice_number"] == "INV2101"
    assert data[0]["supplier_id"] == "SUP001"

    # SUP002 data must not leak.
    assert all(
        invoice["supplier_id"] != "SUP002"
        for invoice in data
    )


def test_supplier_b_get_all_invoices_returns_only_own_invoices():
    """
    R5 Supplier Scoping:

    SUP002 must only receive invoices belonging to SUP002.
    """

    # --------------------------------------------------------
    # Create SUP001 invoice.
    # --------------------------------------------------------

    create_received_po(
        po_number="PO2111",
        supplier_id="SUP001",
    )

    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV2111",
        po_number="PO2111",
        supplier_id="SUP001",
    )

    assert response.status_code == 201, response.text

    # --------------------------------------------------------
    # Create SUP002 invoice.
    # --------------------------------------------------------

    create_received_po(
        po_number="PO2112",
        supplier_id="SUP002",
    )

    authenticate_as(SUPPLIER_2_USER)

    response = create_sample_invoice(
        invoice_number="INV2112",
        po_number="PO2112",
        supplier_id="SUP002",
    )

    assert response.status_code == 201, response.text

    # --------------------------------------------------------
    # Request list as SUP002.
    # --------------------------------------------------------

    authenticate_as(SUPPLIER_2_USER)

    response = client.get(
        "/api/v1/invoices"
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert len(data) == 1

    assert data[0]["invoice_number"] == "INV2112"
    assert data[0]["supplier_id"] == "SUP002"

    # SUP001 must not be exposed.
    assert all(
        invoice["supplier_id"] != "SUP001"
        for invoice in data
    )


# ============================================================
# R5 - SUPPLIER TOKEN WITHOUT SUPPLIER_ID
# ============================================================

def test_supplier_without_supplier_id_is_rejected():
    """
    R5 Supplier Scoping:

    A supplier token without supplier_id must not be allowed
    to access supplier-scoped invoice resources.
    """

    authenticate_as(SUPPLIER_NO_ID_USER)

    response = client.get(
        "/api/v1/invoices/SUP001/INV9999"
    )

    assert response.status_code == 403

    assert (
        response.json()["detail"]
        == "Supplier identity is missing"
    )


def test_supplier_without_supplier_id_cannot_list_invoices():
    """
    A supplier without supplier_id must not be able to
    retrieve the invoice list.
    """

    authenticate_as(SUPPLIER_NO_ID_USER)

    response = client.get(
        "/api/v1/invoices"
    )

    assert response.status_code == 403

    assert (
        response.json()["detail"]
        == "Supplier identity is missing"
    )


# ============================================================
# INVOICE BEFORE GOODS RECEIPT
# ============================================================

def test_invoice_cannot_be_created_before_goods_receipt():
    """
    An invoice must not be created while the P2P workflow
    is still in the acknowledged state.

    Production flow:
        acknowledged -> shipped -> received -> invoiced
    """

    create_acknowledged_po(
        quantity=10,
        unit_price=50000,
    )

    # create_acknowledged_po() leaves the P2P state as
    # acknowledged, so invoice creation must fail.
    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV9001",
        quantity=1,
        amount=50000,
    )

    assert response.status_code == 400

    assert (
        "received"
        in response.json()["detail"].lower()
    )


# ============================================================
# INVOICE STATUS VS P2P STATE
# ============================================================

def test_invoice_status_remains_submitted_after_creation():
    """
    Invoice status and P2P workflow state are separate.

    After invoice creation:
        Invoice status = submitted
        P2P state      = invoiced
    """

    create_received_po(
        quantity=10,
        unit_price=50000,
    )

    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV9003",
        quantity=10,
        amount=500000,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["status"] == "submitted"

    assert (
        p2p_states["PO1001"]
        == P2PState.invoiced
    )


# ============================================================
# EXACT REMAINING INVOICE QUANTITY
# ============================================================

def test_partial_invoice_exact_remaining_quantity_is_allowed():
    """
    After invoicing 7 of 10 units, the remaining 3 units
    may be invoiced successfully.
    """

    create_received_po(
        quantity=10,
        unit_price=50000,
    )

    authenticate_as(SUPPLIER_1_USER)

    response1 = create_sample_invoice(
        invoice_number="INV9101",
        quantity=7,
        amount=350000,
    )

    assert response1.status_code == 201, response1.text

    # Test-only P2P reset so the second invoice can proceed
    # to quantity reconciliation.
    p2p_states["PO1001"] = P2PState.received

    response2 = create_sample_invoice(
        invoice_number="INV9102",
        quantity=3,
        amount=150000,
    )

    assert response2.status_code == 201, response2.text


# ============================================================
# FAILED OVER-INVOICE MUST NOT MODIFY EXISTING INVOICE
# ============================================================

def test_failed_over_invoice_does_not_modify_previous_invoice():
    """
    A failed second invoice must not modify or replace
    the already-created first invoice.
    """

    create_received_po(
        quantity=10,
        unit_price=50000,
    )

    authenticate_as(SUPPLIER_1_USER)

    response1 = create_sample_invoice(
        invoice_number="INV9201",
        quantity=7,
        amount=350000,
    )

    assert response1.status_code == 201, response1.text

    # Test-only P2P reset.
    p2p_states["PO1001"] = P2PState.received

    response2 = create_sample_invoice(
        invoice_number="INV9202",
        quantity=4,
        amount=200000,
    )

    assert response2.status_code == 400

    invoice = invoices[
        ("SUP001", "INV9201")
    ]

    assert invoice["items"][0]["quantity"] == 7

    assert (
        ("SUP001", "INV9202")
        not in invoices
    )


# ============================================================
# UNIT PRICE AT UPPER TOLERANCE
# ============================================================

def test_invoice_unit_price_at_upper_tolerance():
    """
    52,500 is exactly 5% above the PO price of 50,000,
    so it must be accepted.
    """

    create_received_po(
        unit_price=50000,
    )

    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV9301",
        unit_price=52500,
        amount=52500,
    )

    assert response.status_code == 201, response.text


# ============================================================
# UNIT PRICE AT LOWER TOLERANCE
# ============================================================

def test_invoice_unit_price_at_lower_tolerance():
    """
    47,500 is exactly 5% below the PO price of 50,000,
    so it must be accepted.
    """

    create_received_po(
        unit_price=50000,
    )

    authenticate_as(SUPPLIER_1_USER)

    response = create_sample_invoice(
        invoice_number="INV9302",
        unit_price=47500,
        amount=47500,
    )

    assert response.status_code == 201, response.text


# ============================================================
# MULTI-PO INVOICE STATE ROLLBACK
# ============================================================

def test_multi_po_invoice_rolls_back_p2p_transition_on_failure(
    monkeypatch,
):
    """
    If a multi-PO invoice is stored and the P2P transition
    fails part-way through, previously transitioned POs must
    be restored and the invoice must be removed.
    """

    create_acknowledged_po(
        po_number="PO1001",
        supplier_id="SUP001",
        quantity=5,
        unit_price=50000,
    )

    create_acknowledged_po(
        po_number="PO1002",
        supplier_id="SUP001",
        quantity=5,
        unit_price=50000,
    )

    # Both POs must pass the initial P2P invoice validation.
    # We deliberately make the second transition fail later.
    p2p_states["PO1001"] = P2PState.received
    p2p_states["PO1002"] = P2PState.received

    original_transition_p2p = (
        invoice_service.transition_p2p
    )

    def failing_transition(
        po_number,
        target_state,
    ):
        if po_number == "PO1002":
            raise ValueError(
                "Simulated P2P transition failure"
            )

        return original_transition_p2p(
            po_number,
            target_state,
        )

    monkeypatch.setattr(
        invoice_service,
        "transition_p2p",
        failing_transition,
    )

    authenticate_as(SUPPLIER_1_USER)

    payload = {
        "invoice_number": "INV9401",
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
                "po_number": "PO1002",
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

    # PO1001 was transitioned first and must be rolled back.
    assert (
        p2p_states["PO1001"]
        == P2PState.received
    )

    # PO1002 failed before its state changed.
    assert (
        p2p_states["PO1002"]
        == P2PState.received
    )

    # Invoice must not remain stored.
    assert (
        ("SUP001", "INV9401")
        not in invoices
    )


# ============================================================
# SUPPLIER WITHOUT SUPPLIER_ID CANNOT CREATE INVOICE
# ============================================================

def test_supplier_without_supplier_id_cannot_create_invoice():
    """
    A supplier token without supplier_id must be rejected
    before invoice creation.
    """

    # Create the PO first. This helper changes the mocked
    # authentication, so supplier authentication must happen
    # AFTER the helper call.
    create_received_po(
        po_number="PO9501",
        supplier_id="SUP001",
    )

    authenticate_as(SUPPLIER_NO_ID_USER)

    response = create_sample_invoice(
        invoice_number="INV9501",
        po_number="PO9501",
        supplier_id="SUP001",
    )

    assert response.status_code == 403

    assert (
        response.json()["detail"]
        == "Supplier identity is missing"
    )

# ============================================================
# INVOICE DOCUMENT DOWNLOAD - MINIO / PRESIGNED URL TESTS
# ============================================================


def upload_invoice_pdf(
    invoice_number="INV1001",
    supplier_id="SUP001",
):
    """
    Upload a valid PDF to the invoice document endpoint.
    """

    authenticate_as(
        SUPPLIER_1_USER
        if supplier_id == "SUP001"
        else SUPPLIER_2_USER
    )

    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n"
        b"<< /Type /Catalog >>\n"
        b"endobj\n"
        b"%%EOF"
    )

    return client.post(
        f"/api/v1/invoices/{supplier_id}/"
        f"{invoice_number}/document",
        files={
            "file": (
                f"{invoice_number}.pdf",
                BytesIO(pdf_content),
                "application/pdf",
            )
        },
    )


def test_invoice_document_download_returns_presigned_url():
    """
    Supplier can download its own invoice document.

    Expected:
        200
        presigned MinIO URL
        supplier/invoice information
        configured expiry
    """

    create_submitted_invoice()

    upload_response = upload_invoice_pdf()

    assert upload_response.status_code == 200, (
        upload_response.text
    )

    with patch(
        "app.routes.invoice."
        "document_storage_service.generate_download_url"
    ) as mock_generate:

        mock_generate.return_value = (
            "http://127.0.0.1:9000/"
            "supplier-documents/"
            "suppliers/SUP001/invoices/INV1001.pdf"
            "?X-Amz-Expires=300"
        )

        authenticate_as(SUPPLIER_1_USER)

        response = client.get(
            "/api/v1/invoices/"
            "SUP001/INV1001/document"
        )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["invoice_number"] == "INV1001"
    assert data["supplier_id"] == "SUP001"
    assert data["file_name"] == "INV1001.pdf"

    assert data["download_url"].startswith(
        "http://127.0.0.1:9000/"
    )

    assert data["expires_in_seconds"] == 300

    mock_generate.assert_called_once_with(
        object_key=(
            "suppliers/SUP001/"
            "invoices/INV1001.pdf"
        )
    )


def test_invoice_document_download_uses_registered_document_path():
    """
    Download URL generation must use the MinIO object key
    registered against the invoice.
    """

    create_submitted_invoice()

    invoices[
        ("SUP001", "INV1001")
    ]["document_path"] = (
        "suppliers/SUP001/"
        "invoices/INV1001.pdf"
    )

    authenticate_as(SUPPLIER_1_USER)

    with patch(
        "app.routes.invoice."
        "document_storage_service.generate_download_url"
    ) as mock_generate:

        mock_generate.return_value = (
            "http://minio.test/presigned"
        )

        response = client.get(
            "/api/v1/invoices/"
            "SUP001/INV1001/document"
        )

    assert response.status_code == 200

    mock_generate.assert_called_once_with(
        object_key=(
            "suppliers/SUP001/"
            "invoices/INV1001.pdf"
        )
    )


def test_invoice_document_download_cross_supplier_is_forbidden():
    """
    Supplier SUP002 must not receive a download URL for
    SUP001's invoice.
    """

    create_submitted_invoice()

    invoices[
        ("SUP001", "INV1001")
    ]["document_path"] = (
        "suppliers/SUP001/"
        "invoices/INV1001.pdf"
    )

    authenticate_as(SUPPLIER_2_USER)

    with patch(
        "app.routes.invoice."
        "document_storage_service.generate_download_url"
    ) as mock_generate:

        response = client.get(
            "/api/v1/invoices/"
            "SUP001/INV1001/document"
        )

    assert response.status_code == 403

    data = response.json()

    assert "does not own" in data["detail"]

    mock_generate.assert_not_called()


def test_invoice_document_download_cross_supplier_does_not_call_minio():
    """
    Security requirement:

    Cross-supplier access must be rejected BEFORE any
    MinIO presigned URL generation occurs.
    """

    create_submitted_invoice()

    invoices[
        ("SUP001", "INV1001")
    ]["document_path"] = (
        "suppliers/SUP001/"
        "invoices/INV1001.pdf"
    )

    authenticate_as(SUPPLIER_2_USER)

    with patch(
        "app.routes.invoice."
        "document_storage_service.generate_download_url"
    ) as mock_generate:

        response = client.get(
            "/api/v1/invoices/"
            "SUP001/INV1001/document"
        )

    assert response.status_code == 403

    mock_generate.assert_not_called()


def test_invoice_document_download_unknown_invoice_returns_404():
    """
    A supplier requesting a non-existing invoice must receive
    404 rather than a storage error.
    """

    authenticate_as(SUPPLIER_1_USER)

    with patch(
        "app.routes.invoice."
        "document_storage_service.generate_download_url"
    ) as mock_generate:

        response = client.get(
            "/api/v1/invoices/"
            "SUP001/UNKNOWN/document"
        )

    assert response.status_code == 404

    assert response.json()["detail"] == (
        "Invoice not found."
    )

    mock_generate.assert_not_called()


def test_invoice_document_download_without_document_returns_404():
    """
    Existing invoice without a document_path must return 404.
    """

    create_submitted_invoice()

    assert invoices[
        ("SUP001", "INV1001")
    ]["document_path"] is None

    authenticate_as(SUPPLIER_1_USER)

    with patch(
        "app.routes.invoice."
        "document_storage_service.generate_download_url"
    ) as mock_generate:

        response = client.get(
            "/api/v1/invoices/"
            "SUP001/INV1001/document"
        )

    assert response.status_code == 404

    assert response.json()["detail"] == (
        "Document not found."
    )

    mock_generate.assert_not_called()


def test_invoice_document_download_minio_failure_returns_502():
    """
    MinIO presigned URL generation failure must become
    an HTTP 502 response.
    """

    create_submitted_invoice()

    invoices[
        ("SUP001", "INV1001")
    ]["document_path"] = (
        "suppliers/SUP001/"
        "invoices/INV1001.pdf"
    )

    authenticate_as(SUPPLIER_1_USER)

    from app.services.document_storage_service import (
        DocumentDownloadError,
    )

    with patch(
        "app.routes.invoice."
        "document_storage_service.generate_download_url"
    ) as mock_generate:

        mock_generate.side_effect = (
            DocumentDownloadError(
                "Unable to generate document "
                "download URL."
            )
        )

        response = client.get(
            "/api/v1/invoices/"
            "SUP001/INV1001/document"
        )

    assert response.status_code == 502

    assert response.json()["detail"] == (
        "Unable to generate document "
        "download URL."
    )


def test_invoice_document_download_requires_authentication():
    """
    Unauthenticated users cannot request invoice documents.
    """

    create_submitted_invoice()

    app.dependency_overrides.pop(
        verify_token,
        None,
    )

    response = client.get(
        "/api/v1/invoices/"
        "SUP001/INV1001/document"
    )

    assert response.status_code == 401


def test_invoice_document_download_procurement_manager_allowed():
    """
    Non-supplier roles are not supplier-scoped.

    Procurement manager can access the invoice document
    endpoint according to the current dependency rules.
    """

    create_submitted_invoice()

    invoices[
        ("SUP001", "INV1001")
    ]["document_path"] = (
        "suppliers/SUP001/"
        "invoices/INV1001.pdf"
    )

    authenticate_as(PROCUREMENT_USER)

    with patch(
        "app.routes.invoice."
        "document_storage_service.generate_download_url"
    ) as mock_generate:

        mock_generate.return_value = (
            "http://minio.test/presigned"
        )

        response = client.get(
            "/api/v1/invoices/"
            "SUP001/INV1001/document"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["invoice_number"] == "INV1001"
    assert data["supplier_id"] == "SUP001"

    mock_generate.assert_called_once_with(
        object_key=(
            "suppliers/SUP001/"
            "invoices/INV1001.pdf"
        )
    )


def test_invoice_document_download_supplier_without_supplier_id_returns_403():
    """
    A supplier token without supplier_id must not be allowed
    to access any invoice document.
    """

    create_submitted_invoice()

    authenticate_as(
        SUPPLIER_NO_ID_USER
    )

    with patch(
        "app.routes.invoice."
        "document_storage_service.generate_download_url"
    ) as mock_generate:

        response = client.get(
            "/api/v1/invoices/"
            "SUP001/INV1001/document"
        )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "Supplier identity is missing"
    )

    mock_generate.assert_not_called()


def test_invoice_document_download_invalid_invoice_number_returns_400():
    """
    Invalid invoice numbers must be rejected by the service
    validation.
    """

    authenticate_as(SUPPLIER_1_USER)

    with patch(
        "app.routes.invoice."
        "document_storage_service.generate_download_url"
    ) as mock_generate:

        response = client.get(
            "/api/v1/invoices/"
            "SUP001/INVALID%20INVOICE/document"
        )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "Invalid invoice number."
    )

    mock_generate.assert_not_called()

def test_invoice_document_download_object_exists_minio_failure_returns_502():
    create_submitted_invoice(
        invoice_number="INV9910",
    )

    object_key = (
        "suppliers/SUP001/invoices/INV9910.pdf"
    )

    invoices[
        ("SUP001", "INV9910")
    ]["document_path"] = object_key

    authenticate_as(SUPPLIER_1_USER)

    with patch.object(
        invoice_service.document_storage_service,
        "object_exists",
        side_effect=DocumentStorageError(
            "Unable to check MinIO object."
        ),
    ) as mock_exists:

        response = client.get(
            "/api/v1/invoices/SUP001/INV9910/document"
        )

    assert response.status_code == 502, response.text

    mock_exists.assert_called_once_with(
        object_key=object_key,
    )
def test_invoice_document_download_presign_failure_returns_502():
    create_submitted_invoice(
        invoice_number="INV9911",
    )

    object_key = (
        "suppliers/SUP001/invoices/INV9911.pdf"
    )

    invoices[
        ("SUP001", "INV9911")
    ]["document_path"] = object_key

    authenticate_as(SUPPLIER_1_USER)

    with patch.object(
        invoice_service.document_storage_service,
        "object_exists",
        return_value=True,
    ):

        with patch.object(
            invoice_service.document_storage_service,
            "generate_download_url",
            side_effect=DocumentDownloadError(
                "Unable to generate download URL."
            ),
        ) as mock_download:

            response = client.get(
                "/api/v1/invoices/SUP001/INV9911/document"
            )

    assert response.status_code == 502, response.text

    mock_download.assert_called_once_with(
        object_key=object_key,
    )