import pytest

from app.schemas.purchase_order import PurchaseOrderStatus
from app.schemas.invoice import InvoiceStatus

from app.services.purchase_order_service import (
    purchase_orders,
    po_events,
)

from app.services.invoice_service import (
    invoices,
    invoice_events,
)

from app.services.goods_receipt_service import goods_receipts
from app.services.shipment_service import shipments

from app.services.po_p2p_state_machine import (
    P2PState,
    p2p_states,
)

from app.services.three_way_match_service import (
    three_way_matches,
)


# ============================================================
# RESET ALL IN-MEMORY DATA
# ============================================================

@pytest.fixture(autouse=True)
def reset_data():
    """
    Reset all in-memory stores before every test.

    Authentication is handled by the role-specific
    TestClient fixtures from conftest.py.
    """

    purchase_orders.clear()
    po_events.clear()

    invoices.clear()
    invoice_events.clear()

    goods_receipts.clear()
    shipments.clear()

    p2p_states.clear()
    three_way_matches.clear()

    yield

    purchase_orders.clear()
    po_events.clear()

    invoices.clear()
    invoice_events.clear()

    goods_receipts.clear()
    shipments.clear()

    p2p_states.clear()
    three_way_matches.clear()



# ============================================================
# TEST DATA HELPERS
# ============================================================

def create_fulfilled_po(
    po_number="PO1001",
    supplier_id="SUP001",
    quantity=10,
    unit_price=100.0,
    item_code="LAP001",
):
    purchase_orders[po_number] = {
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
        "status": PurchaseOrderStatus.fulfilled,
        "created_at": "2026-09-09T08:00:00",
        "expected_delivery": "2026-09-15",
        "actual_delivery_date": "2026-09-09",
        "history": [],
    }

    p2p_states[po_number] = P2PState.invoiced

    return purchase_orders[po_number]

def create_invoice_via_api(
    client,
    invoice_number="INV1001",
    po_number="PO1001",
    supplier_id="SUP001",
    item_code="LAP001",
    quantity=10,
    unit_price=100.0,
    amount=None,
):
    if amount is None:
        amount = quantity * unit_price

    return client.post(
        "/api/v1/invoices",
        json={
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
            "invoice_date": "2026-09-09",
        },
    )

def create_received_goods_receipt(
    po_number="PO1001",
    supplier_id="SUP001",
    quantity=10,
    item_code="LAP001",
):
    receipt_id = f"GR-{po_number}"

    goods_receipts[receipt_id] = {
        "receipt_id": receipt_id,
        "po_number": po_number,
        "supplier_id": supplier_id,
        "receipt_date": "2026-09-09",
        "warehouse": "WH-HYD-01",
        "received_by": "warehouse.user@company.com",
        "items": [
            {
                "item_code": item_code,
                "quantity": quantity,
            }
        ],
        "status": "received",
    }

    return goods_receipts[receipt_id]


def create_submitted_invoice(
    invoice_number="INV1001",
    supplier_id="SUP001",
    po_number="PO1001",
    quantity=10,
    unit_price=100.0,
    item_code="LAP001",
):
    amount = quantity * unit_price

    invoice_key = (supplier_id, invoice_number)

    invoices[invoice_key] = {
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
        "invoice_date": "2026-09-09",
        "document_url": None,
        "document_path": None,
        "status": InvoiceStatus.submitted,
        "dispute": None,
        "history": [],
    }

    return invoices[invoice_key]


def prepare_exact_match(
    po_number="PO1001",
    invoice_number="INV1001",
    supplier_id="SUP001",
):
    create_fulfilled_po(
        po_number=po_number,
        supplier_id=supplier_id,
        quantity=10,
        unit_price=100.0,
    )

    create_received_goods_receipt(
        po_number=po_number,
        supplier_id=supplier_id,
        quantity=10,
    )

    create_submitted_invoice(
        invoice_number=invoice_number,
        supplier_id=supplier_id,
        po_number=po_number,
        quantity=10,
        unit_price=100.0,
    )


def match_url(
    supplier_id="SUP001",
    invoice_number="INV1001",
):
    return (
        f"/api/v1/three-way-matches/"
        f"{supplier_id}/{invoice_number}"
    )


def resolve_url(
    supplier_id="SUP001",
    invoice_number="INV1001",
):
    return (
        f"/api/v1/three-way-matches/"
        f"{supplier_id}/{invoice_number}/resolve"
    )


def payment_approve_url(
    supplier_id="SUP001",
    invoice_number="INV1001",
):
    return (
        f"/api/v1/three-way-matches/"
        f"{supplier_id}/{invoice_number}/payment-approve"
    )

def resolution_suggestion_url(
    supplier_id="SUP001",
    invoice_number="INV1001",
):
    return (
        f"/api/v1/three-way-matches/"
        f"{supplier_id}/{invoice_number}/resolution-suggestion"
    )

# ============================================================
# 1. EXACT 3-WAY MATCH
# ============================================================

def test_exact_three_way_match(
    procurement_client,
):
    prepare_exact_match()

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200

    data = response.json()

    assert data["supplier_id"] == "SUP001"
    assert data["invoice_number"] == "INV1001"
    assert data["status"] == "matched"

    assert data["lines"][0]["po_quantity"] == 10
    assert data["lines"][0]["received_quantity"] == 10
    assert data["lines"][0]["invoiced_quantity"] == 10

    assert data["lines"][0]["po_unit_price"] == 100
    assert data["lines"][0]["invoice_unit_price"] == 100

    assert data["lines"][0]["quantity_matched"] is True
    assert data["lines"][0]["price_matched"] is True

    assert p2p_states["PO1001"] == P2PState.matched


# ============================================================
# 2. SUPPLIER CANNOT EXECUTE THREE-WAY MATCH
# ============================================================

def test_supplier_cannot_execute_three_way_match(
    supplier_client,
):
    prepare_exact_match()

    response = supplier_client.post(
        match_url()
    )

    assert response.status_code == 403

    assert p2p_states["PO1001"] == P2PState.invoiced


# ============================================================
# 3. PO QUANTITY MISMATCH
# ============================================================

def test_po_quantity_mismatch(
    procurement_client,
):
    prepare_exact_match()

    purchase_orders["PO1001"]["items"][0]["quantity"] = 12

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "discrepancy"
    assert "quantity_mismatch" in data["discrepancies"]

    assert p2p_states["PO1001"] == P2PState.discrepancy


# ============================================================
# 4. GOODS RECEIPT QUANTITY MISMATCH
# ============================================================

def test_goods_receipt_quantity_mismatch(
    procurement_client,
):
    prepare_exact_match()

    goods_receipts[
        "GR-PO1001"
    ]["items"][0]["quantity"] = 8

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "discrepancy"
    assert "quantity_mismatch" in data["discrepancies"]

    assert p2p_states["PO1001"] == P2PState.discrepancy


# ============================================================
# 5. INVOICE QUANTITY MISMATCH
# ============================================================

def test_invoice_quantity_mismatch(
    procurement_client,
):
    prepare_exact_match()

    invoices[
        ("SUP001", "INV1001")
    ]["items"][0]["quantity"] = 5

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "discrepancy"
    assert "quantity_mismatch" in data["discrepancies"]

    assert p2p_states["PO1001"] == P2PState.discrepancy


# ============================================================
# 6. PRICE BELOW 5% DIFFERENCE
# ============================================================

def test_price_difference_below_five_percent_is_matched(
    procurement_client,
):
    prepare_exact_match()

    invoices[
        ("SUP001", "INV1001")
    ]["items"][0]["unit_price"] = 104.0

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "matched"
    assert data["lines"][0]["price_matched"] is True

    assert p2p_states["PO1001"] == P2PState.matched


# ============================================================
# 7. PRICE EXACTLY 5%
# ============================================================

def test_price_difference_exactly_five_percent_is_matched(
    procurement_client,
):
    prepare_exact_match()

    invoices[
        ("SUP001", "INV1001")
    ]["items"][0]["unit_price"] = 105.0

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "matched"
    assert data["lines"][0]["price_matched"] is True

    assert p2p_states["PO1001"] == P2PState.matched


# ============================================================
# 8. PRICE ABOVE 5%
# ============================================================

# ============================================================
# 8. PRICE ABOVE 5%
# ============================================================

def test_price_difference_above_five_percent_is_discrepancy(
    supplier_client,
    procurement_client,
):
    create_fulfilled_po(
        quantity=10,
        unit_price=100.0,
    )

    create_received_goods_receipt(
        quantity=10,
    )

    # The invoice API expects the P2P state to be
    # "received" before invoice creation.
    # Invoice creation will transition it to "invoiced".
    p2p_states["PO1001"] = P2PState.received

    invoice_response = create_invoice_via_api(
        supplier_client,
        invoice_number="INV1001",
        quantity=10,
        unit_price=106.0,
        amount=1060.0,
    )

    assert invoice_response.status_code in (
        200,
        201,
    ), invoice_response.text

    # Invoice creation must move the P2P state:
    # received -> invoiced
    assert p2p_states["PO1001"] == P2PState.invoiced

    response = procurement_client.post(
        match_url(),
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["status"] == "discrepancy"
    assert "price_mismatch" in data["discrepancies"]

    assert p2p_states["PO1001"] == P2PState.discrepancy

# ============================================================
# 9. QUANTITY + PRICE MISMATCH
# ============================================================

def test_quantity_and_price_mismatch(
    supplier_client,
    procurement_client,
):
    create_fulfilled_po(
        quantity=10,
        unit_price=100.0,
    )

    create_received_goods_receipt(
        quantity=10,
    )

    # The invoice API requires the PO to be in
    # the "received" P2P state before invoice creation.
    p2p_states["PO1001"] = P2PState.received

    invoice_response = create_invoice_via_api(
        supplier_client,
        invoice_number="INV1001",
        quantity=5,
        unit_price=106.0,
        amount=530.0,
    )

    assert invoice_response.status_code in (
        200,
        201,
    ), invoice_response.text

    # Invoice creation should transition:
    # received -> invoiced
    assert p2p_states["PO1001"] == P2PState.invoiced

    response = procurement_client.post(
        match_url(),
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["status"] == "discrepancy"

    assert "quantity_mismatch" in data["discrepancies"]
    assert "price_mismatch" in data["discrepancies"]

    assert p2p_states["PO1001"] == P2PState.discrepancy

# ============================================================
# 10. MISSING INVOICE
# ============================================================

def test_missing_invoice_returns_error(
    procurement_client,
):
    create_fulfilled_po()
    create_received_goods_receipt()

    response = procurement_client.post(
        match_url(
            supplier_id="SUP001",
            invoice_number="INV-NOT-FOUND",
        )
    )

    assert response.status_code in (404, 400)
    assert "not found" in response.text.lower()


# ============================================================
# 11. MISSING PO
# ============================================================

def test_missing_po_returns_error(
    procurement_client,
):
    create_submitted_invoice(
        invoice_number="INV1001",
        supplier_id="SUP001",
        po_number="PO-NOT-FOUND",
    )

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code in (404, 400)
    assert "po" in response.text.lower()


# ============================================================
# 12. WRONG SUPPLIER / CROSS-SUPPLIER ACCESS
# ============================================================

def test_supplier_cannot_match_other_supplier_invoice(
    supplier_client,
):
    prepare_exact_match(
        supplier_id="SUP002",
    )

    response = supplier_client.post(
        match_url(
            supplier_id="SUP002",
            invoice_number="INV1001",
        )
    )

    assert response.status_code == 403


# ============================================================
# 13. INVOICE WRONG STATUS
# ============================================================

@pytest.mark.parametrize(
    "invoice_status",
    [
        InvoiceStatus.approved,
        InvoiceStatus.rejected,
        InvoiceStatus.disputed,
        InvoiceStatus.adjusted,
    ],
)
def test_invoice_must_be_submitted(
    invoice_status,
    procurement_client,
):
    prepare_exact_match()

    invoices[
        ("SUP001", "INV1001")
    ]["status"] = invoice_status

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code in (400, 409)
    assert "submitted" in response.text.lower()


# ============================================================
# 14. PO WRONG STATUS
# ============================================================

def test_po_must_be_fulfilled(
    procurement_client,
):
    prepare_exact_match()

    purchase_orders[
        "PO1001"
    ]["status"] = PurchaseOrderStatus.acknowledged

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code in (400, 409)
    assert "fulfilled" in response.text.lower()


# ============================================================
# 15. P2P WRONG STATUS
# ============================================================

@pytest.mark.parametrize(
    "wrong_state",
    [
        P2PState.received,
        P2PState.acknowledged,
        P2PState.shipped,
        P2PState.matched,
        P2PState.discrepancy,
        P2PState.payment_approved,
    ],
)
def test_p2p_must_be_invoiced(
    wrong_state,
    procurement_client,
):
    prepare_exact_match()

    p2p_states[
        "PO1001"
    ] = wrong_state

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code in (400, 409)
    assert "invoiced" in response.text.lower()


# ============================================================
# 16. REPEATED MATCH
# ============================================================

def test_repeated_match_is_rejected(
    procurement_client,
):
    prepare_exact_match()

    first_response = procurement_client.post(
        match_url()
    )

    assert first_response.status_code == 200
    assert p2p_states["PO1001"] == P2PState.matched

    second_response = procurement_client.post(
        match_url()
    )

    assert second_response.status_code in (400, 409)


# ============================================================
# 17. MATCH RESULT PERSISTENCE
# ============================================================

def test_match_result_is_persisted(
    procurement_client,
    supplier_client,
):
    prepare_exact_match()

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200

    data = response.json()

    match_id = data["match_id"]

    assert any(
        match.get("match_id") == match_id
        for match in three_way_matches.values()
    )

    get_response = supplier_client.get(
        match_url()
    )

    assert get_response.status_code == 200

    stored = get_response.json()

    assert stored["match_id"] == match_id
    assert stored["status"] == "matched"


# ============================================================
# 18. DISCREPANCY DETAILS
# ============================================================

def test_discrepancy_contains_correct_line_details(
    procurement_client,
):
    prepare_exact_match()

    invoice = invoices[
        ("SUP001", "INV1001")
    ]

    invoice["items"][0]["quantity"] = 5
    invoice["items"][0]["unit_price"] = 106.0

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200

    data = response.json()

    line = data["lines"][0]

    assert line["po_quantity"] == 10
    assert line["received_quantity"] == 10
    assert line["invoiced_quantity"] == 5

    assert line["po_unit_price"] == 100
    assert line["invoice_unit_price"] == 106

    assert line["quantity_matched"] is False
    assert line["price_matched"] is False

    assert "quantity_mismatch" in line["discrepancies"]
    assert "price_mismatch" in line["discrepancies"]


# ============================================================
# 19. COMPLIANCE OFFICER RESOLVES DISCREPANCY
# ============================================================

def test_compliance_officer_can_resolve_discrepancy(
    procurement_client,
    compliance_client,
):
    prepare_exact_match()

    invoices[
        ("SUP001", "INV1001")
    ]["items"][0]["quantity"] = 5

    match_response = procurement_client.post(
        match_url()
    )

    assert match_response.status_code == 200
    assert match_response.json()["status"] == "discrepancy"

    response = compliance_client.post(
        resolve_url(),
        json={
            "reason": (
                "Approved after manual compliance review."
            ),
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "matched"

    assert p2p_states["PO1001"] == P2PState.matched


# ============================================================
# 20. RESOLUTION WITHOUT DISCREPANCY
# ============================================================

def test_resolution_without_discrepancy_fails(
    procurement_client,
    compliance_client,
):
    prepare_exact_match()

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200
    assert response.json()["status"] == "matched"

    response = compliance_client.post(
        resolve_url(),
        json={
            "reason": (
                "Attempted unnecessary resolution."
            ),
        },
    )

    assert response.status_code in (400, 409)


# ============================================================
# 21. INVALID / EMPTY RESOLUTION REASON
# ============================================================

def test_resolution_requires_valid_reason(
    procurement_client,
    compliance_client,
):
    prepare_exact_match()

    invoices[
        ("SUP001", "INV1001")
    ]["items"][0]["quantity"] = 5

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200
    assert response.json()["status"] == "discrepancy"

    response = compliance_client.post(
        resolve_url(),
        json={
            "reason": "",
        },
    )

    assert response.status_code == 422


# ============================================================
# 22. UNAUTHORIZED RESOLUTION
# ============================================================

def test_supplier_cannot_resolve_discrepancy(
    supplier_client,
    procurement_client,
):
    prepare_exact_match()

    # Create a quantity discrepancy in the stored invoice.
    invoice = invoices[("SUP001", "INV1001")]
    invoice["items"][0]["quantity"] = 5

    # Procurement Manager performs the three-way match.
    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200
    assert response.json()["status"] == "discrepancy"

    # Supplier must not be allowed to resolve the discrepancy.
    response = supplier_client.post(
        resolve_url(),
        json={
            "reason": "Supplier attempted to resolve the discrepancy."
        },
    )

    assert response.status_code == 403
# ============================================================
# 23. SUCCESSFUL PAYMENT APPROVAL
# ============================================================

def test_payment_approval_after_match(
    procurement_client,
):
    prepare_exact_match()

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200
    assert response.json()["status"] == "matched"

    response = procurement_client.post(
        payment_approve_url()
    )

    assert response.status_code == 200

    data = response.json()

    assert data["payment_status"] == "payment_approved"
    assert data["approved_by"] == (
        "procurementmanager@company.com"
    )
    assert data["approved_role"] == "procurement_manager"

    assert p2p_states["PO1001"] == P2PState.payment_approved


# ============================================================
# 24. PAYMENT APPROVAL FROM DISCREPANCY
# ============================================================

def test_payment_approval_from_discrepancy_fails(
    procurement_client,
):
    prepare_exact_match()

    invoices[
        ("SUP001", "INV1001")
    ]["items"][0]["quantity"] = 5

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200
    assert response.json()["status"] == "discrepancy"

    response = procurement_client.post(
        payment_approve_url()
    )

    assert response.status_code in (400, 409)

    assert (
        p2p_states["PO1001"]
        == P2PState.discrepancy
    )


# ============================================================
# 25. PAYMENT APPROVAL BEFORE MATCH
# ============================================================

def test_payment_approval_before_match_fails(
    procurement_client,
):
    prepare_exact_match()

    response = procurement_client.post(
        payment_approve_url()
    )

    assert response.status_code == 404

    assert "three-way match record not found" in (
        response.text.lower()
    )

    assert (
        p2p_states["PO1001"]
        == P2PState.invoiced
    )


# ============================================================
# 26. UNAUTHORIZED PAYMENT APPROVAL
# ============================================================

def test_non_procurement_user_cannot_approve_payment(
    supplier_client,
):
    prepare_exact_match()

    response = supplier_client.post(
        payment_approve_url()
    )

    assert response.status_code == 403


# ============================================================
# 27. DUPLICATE PAYMENT APPROVAL
# ============================================================

def test_duplicate_payment_approval_fails(
    procurement_client,
):
    prepare_exact_match()

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200

    first_response = procurement_client.post(
        payment_approve_url()
    )

    assert first_response.status_code == 200

    assert (
        p2p_states["PO1001"]
        == P2PState.payment_approved
    )

    second_response = procurement_client.post(
        payment_approve_url()
    )

    assert second_response.status_code in (400, 409)


# ============================================================
# 28. MATCHED -> PAYMENT APPROVED
# ============================================================

def test_p2p_moves_from_matched_to_payment_approved(
    procurement_client,
):
    prepare_exact_match()

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200

    assert (
        p2p_states["PO1001"]
        == P2PState.matched
    )

    response = procurement_client.post(
        payment_approve_url()
    )

    assert response.status_code == 200

    assert (
        p2p_states["PO1001"]
        == P2PState.payment_approved
    )


# ============================================================
# 29. MULTIPLE INVOICE ITEMS
# ============================================================

def test_multiple_invoice_items_match(
    procurement_client,
):
    purchase_orders["PO1001"] = {
        "po_number": "PO1001",
        "supplier_id": "SUP001",
        "items": [
            {
                "item_code": "LAP001",
                "description": "Laptop",
                "quantity": 10,
                "unit_price": 100,
            },
            {
                "item_code": "MOU001",
                "description": "Mouse",
                "quantity": 10,
                "unit_price": 20,
            },
        ],
        "total_amount": 1200,
        "status": PurchaseOrderStatus.fulfilled,
        "created_at": "2026-09-09T08:00:00",
        "expected_delivery": "2026-09-15",
        "actual_delivery_date": "2026-09-09",
        "history": [],
    }

    p2p_states["PO1001"] = P2PState.invoiced

    goods_receipts["GR-PO1001"] = {
        "receipt_id": "GR-PO1001",
        "po_number": "PO1001",
        "supplier_id": "SUP001",
        "receipt_date": "2026-09-09",
        "warehouse": "WH-HYD-01",
        "received_by": "warehouse.user@company.com",
        "items": [
            {
                "item_code": "LAP001",
                "quantity": 10,
            },
            {
                "item_code": "MOU001",
                "quantity": 10,
            },
        ],
        "status": "received",
    }

    invoices[("SUP001", "INV1001")] = {
        "invoice_number": "INV1001",
        "supplier_id": "SUP001",
        "items": [
            {
                "po_number": "PO1001",
                "item_code": "LAP001",
                "description": "Laptop",
                "quantity": 10,
                "unit_price": 100,
            },
            {
                "po_number": "PO1001",
                "item_code": "MOU001",
                "description": "Mouse",
                "quantity": 10,
                "unit_price": 20,
            },
        ],
        "amount": 1200,
        "invoice_date": "2026-09-09",
        "status": InvoiceStatus.submitted,
        "document_url": None,
        "document_path": None,
        "dispute": None,
        "history": [],
    }

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "matched"
    assert len(data["lines"]) == 2

    assert p2p_states["PO1001"] == P2PState.matched


# ============================================================
# 30. MULTIPLE POS IN ONE INVOICE
# ============================================================

def test_multiple_pos_in_one_invoice_match(
    procurement_client,
):
    create_fulfilled_po(
        po_number="PO1001",
        supplier_id="SUP001",
    )

    create_fulfilled_po(
        po_number="PO1002",
        supplier_id="SUP001",
    )

    create_received_goods_receipt(
        po_number="PO1001",
        supplier_id="SUP001",
        quantity=10,
    )

    create_received_goods_receipt(
        po_number="PO1002",
        supplier_id="SUP001",
        quantity=10,
    )

    invoices[("SUP001", "INV1001")] = {
        "invoice_number": "INV1001",
        "supplier_id": "SUP001",
        "items": [
            {
                "po_number": "PO1001",
                "item_code": "LAP001",
                "description": "Laptop",
                "quantity": 10,
                "unit_price": 100,
            },
            {
                "po_number": "PO1002",
                "item_code": "LAP001",
                "description": "Laptop",
                "quantity": 10,
                "unit_price": 100,
            },
        ],
        "amount": 2000,
        "invoice_date": "2026-09-09",
        "status": InvoiceStatus.submitted,
        "document_url": None,
        "document_path": None,
        "dispute": None,
        "history": [],
    }

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "matched"

    assert (
        p2p_states["PO1001"]
        == P2PState.matched
    )

    assert (
        p2p_states["PO1002"]
        == P2PState.matched
    )


# ============================================================
# 31. MULTI-PO DISCREPANCY / STATE SAFETY
# ============================================================

def test_multi_po_discrepancy_moves_all_referenced_pos_to_discrepancy(
    procurement_client,
):
    create_fulfilled_po(
        po_number="PO1001",
        supplier_id="SUP001",
    )

    create_fulfilled_po(
        po_number="PO1002",
        supplier_id="SUP001",
    )

    create_received_goods_receipt(
        po_number="PO1001",
        supplier_id="SUP001",
        quantity=10,
    )

    create_received_goods_receipt(
        po_number="PO1002",
        supplier_id="SUP001",
        quantity=10,
    )

    invoices[("SUP001", "INV1001")] = {
        "invoice_number": "INV1001",
        "supplier_id": "SUP001",
        "items": [
            {
                "po_number": "PO1001",
                "item_code": "LAP001",
                "description": "Laptop",
                "quantity": 10,
                "unit_price": 100,
            },
            {
                "po_number": "PO1002",
                "item_code": "LAP001",
                "description": "Laptop",
                "quantity": 5,
                "unit_price": 100,
            },
        ],
        "amount": 1500,
        "invoice_date": "2026-09-09",
        "status": InvoiceStatus.submitted,
        "document_url": None,
        "document_path": None,
        "dispute": None,
        "history": [],
    }

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "discrepancy"

    assert (
        p2p_states["PO1001"]
        == P2PState.discrepancy
    )

    assert (
        p2p_states["PO1002"]
        == P2PState.discrepancy
    )


# ============================================================
# 33. INTERNAL PROCUREMENT MANAGER CAN ACCESS
# ============================================================

def test_procurement_manager_can_access_supplier_match(
    procurement_client,
):
    prepare_exact_match(
        supplier_id="SUP002",
    )

    response = procurement_client.post(
        match_url(
            supplier_id="SUP002",
            invoice_number="INV1001",
        )
    )

    assert response.status_code == 200

    response = procurement_client.get(
        match_url(
            supplier_id="SUP002",
            invoice_number="INV1001",
        )
    )

    assert response.status_code == 200
    assert response.json()["status"] == "matched"


# ============================================================
# 34. MATCH METADATA
# ============================================================

def test_match_metadata_is_created(
    procurement_client,
):
    prepare_exact_match()

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200

    data = response.json()

    assert data["match_id"]
    assert data["created_at"]
    assert data["created_by"] == (
        "procurementmanager@company.com"
    )


# ============================================================
# 35. RESOLUTION METADATA
# ============================================================

def test_resolution_metadata_is_recorded(
    procurement_client,
    compliance_client,
):
    prepare_exact_match()

    invoices[
        ("SUP001", "INV1001")
    ]["items"][0]["quantity"] = 5

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200
    assert response.json()["status"] == "discrepancy"

    response = compliance_client.post(
        resolve_url(),
        json={
            "reason": (
                "Manual compliance review completed."
            ),
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "matched"

    stored_match = next(
        match
        for match in three_way_matches.values()
        if match["invoice_number"] == "INV1001"
    )

    assert stored_match["resolution"]["reason"] == (
        "Manual compliance review completed."
    )

    assert stored_match["resolution"]["resolved_by"]

    assert stored_match["resolution"]["resolved_role"] == (
        "compliance_officer"
    )

    assert stored_match["resolved_by"]


# ============================================================
# 36. PAYMENT APPROVAL METADATA
# ============================================================

def test_payment_approval_metadata_is_recorded(
    procurement_client,
):
    prepare_exact_match()

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200

    response = procurement_client.post(
        payment_approve_url()
    )

    assert response.status_code == 200

    data = response.json()

    assert data["payment_status"] == "payment_approved"
    assert data["approved_at"]
    assert data["approved_by"] == (
        "procurementmanager@company.com"
    )
    assert data["approved_role"] == "procurement_manager"


# ============================================================
# 37. MISSING GOODS RECEIPT
# ============================================================

def test_missing_goods_receipt_creates_discrepancy(
    procurement_client,
):
    create_fulfilled_po()

    create_submitted_invoice()

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "discrepancy"
    assert "quantity_mismatch" in data["discrepancies"]

    assert p2p_states["PO1001"] == P2PState.discrepancy


# ============================================================
# 38. MATCH AFTER PAYMENT APPROVAL
# ============================================================

def test_match_after_payment_approval_fails(
    procurement_client,
):
    prepare_exact_match()

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200

    response = procurement_client.post(
        payment_approve_url()
    )

    assert response.status_code == 200

    assert (
        p2p_states["PO1001"]
        == P2PState.payment_approved
    )

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code in (400, 409)


# ============================================================
# 39. PAYMENT APPROVAL DOES NOT CHANGE DISCREPANCY
# ============================================================

def test_payment_approval_failure_keeps_discrepancy_state(
    procurement_client,
):
    prepare_exact_match()

    invoices[
        ("SUP001", "INV1001")
    ]["items"][0]["quantity"] = 5

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200
    assert response.json()["status"] == "discrepancy"

    response = procurement_client.post(
        payment_approve_url()
    )

    assert response.status_code in (400, 409)

    assert (
        p2p_states["PO1001"]
        == P2PState.discrepancy
    )


# ============================================================
# 40. MULTI-PO MIXED MATCH RESULT
# ============================================================

def test_multi_po_mixed_result_is_discrepancy(
    procurement_client,
):
    create_fulfilled_po(
        po_number="PO1001",
        supplier_id="SUP001",
    )

    create_fulfilled_po(
        po_number="PO1002",
        supplier_id="SUP001",
    )

    create_received_goods_receipt(
        po_number="PO1001",
        supplier_id="SUP001",
        quantity=10,
    )

    create_received_goods_receipt(
        po_number="PO1002",
        supplier_id="SUP001",
        quantity=10,
    )

    invoices[("SUP001", "INV1001")] = {
        "invoice_number": "INV1001",
        "supplier_id": "SUP001",
        "items": [
            {
                "po_number": "PO1001",
                "item_code": "LAP001",
                "description": "Laptop",
                "quantity": 10,
                "unit_price": 100,
            },
            {
                "po_number": "PO1002",
                "item_code": "LAP001",
                "description": "Laptop",
                "quantity": 5,
                "unit_price": 100,
            },
        ],
        "amount": 1500,
        "invoice_date": "2026-09-09",
        "status": InvoiceStatus.submitted,
        "document_url": None,
        "document_path": None,
        "dispute": None,
        "history": [],
    }

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "discrepancy"

    assert (
        p2p_states["PO1001"]
        == P2PState.discrepancy
    )

    assert (
        p2p_states["PO1002"]
        == P2PState.discrepancy
    )


# ============================================================
# 41. SUPPLIER WITHOUT SUPPLIER_ID CANNOT ACCESS MATCH
# ============================================================

def test_supplier_without_supplier_id_is_rejected(
    supplier_no_id_client,
):
    prepare_exact_match()

    response = supplier_no_id_client.get(
        match_url(
            supplier_id="SUP001",
            invoice_number="INV1001",
        )
    )

    assert response.status_code == 403

    assert "supplier id is required" in (
        response.text.lower()
    )

# ============================================================
# 42. SUPPLIER CANNOT GET OTHER SUPPLIER MATCH
# ============================================================

def test_supplier_cannot_get_other_supplier_match(
    supplier_client,
    procurement_client,
):
    # Create and store a match belonging to SUP002.
    prepare_exact_match(
        supplier_id="SUP002",
    )

    # Procurement Manager creates the match.
    response = procurement_client.post(
        match_url(
            supplier_id="SUP002",
            invoice_number="INV1001",
        )
    )

    assert response.status_code == 200

    # SUP001 supplier attempts to access SUP002 match.
    response = supplier_client.get(
        match_url(
            supplier_id="SUP002",
            invoice_number="INV1001",
        )
    )

    assert response.status_code == 403


# ============================================================
# 43. SUPPLIER CAN GET OWN MATCH
# ============================================================

def test_supplier_can_get_own_match(
    supplier_client,
    procurement_client,
):
    prepare_exact_match(
        supplier_id="SUP001",
    )

    # Internal user creates the match.
    response = procurement_client.post(
        match_url(
            supplier_id="SUP001",
            invoice_number="INV1001",
        )
    )

    assert response.status_code == 200

    # SUP001 supplier accesses own match.
    response = supplier_client.get(
        match_url(
            supplier_id="SUP001",
            invoice_number="INV1001",
        )
    )

    assert response.status_code == 200
    assert response.json()["supplier_id"] == "SUP001"
    assert response.json()["invoice_number"] == "INV1001"


# ============================================================
# 44. UNKNOWN THREE-WAY MATCH RETURNS 404
# ============================================================

def test_unknown_three_way_match_returns_404(
    supplier_client,
):
    response = supplier_client.get(
        match_url(
            supplier_id="SUP001",
            invoice_number="INV-NOT-FOUND",
        )
    )

    assert response.status_code == 404

    assert "three-way match record not found" in (
        response.text.lower()
    )


# ============================================================
# 45. UNKNOWN SUPPLIER MATCH RETURNS 404
# ============================================================
def test_unknown_supplier_match_returns_403(
    supplier_client,
):
    response = supplier_client.get(
        match_url(
            supplier_id="SUP-UNKNOWN",
            invoice_number="INV1001",
        )
    )

    assert response.status_code == 403

    assert "forbidden" in response.text.lower()

def test_unknown_match_for_own_supplier_returns_404(
    supplier_client,
):
    response = supplier_client.get(
        match_url(
            supplier_id="SUP001",
            invoice_number="INV-DOES-NOT-EXIST",
        )
    )

    assert response.status_code == 404

    assert "three-way match record not found" in (
        response.text.lower()
    )

# ============================================================
# 46. PROCUREMENT MANAGER CAN GET OTHER SUPPLIER MATCH
# ============================================================

def test_procurement_manager_can_get_other_supplier_match(
    procurement_client,
):
    prepare_exact_match(
        supplier_id="SUP002",
    )

    response = procurement_client.post(
        match_url(
            supplier_id="SUP002",
            invoice_number="INV1001",
        )
    )

    assert response.status_code == 200

    response = procurement_client.get(
        match_url(
            supplier_id="SUP002",
            invoice_number="INV1001",
        )
    )

    assert response.status_code == 200
    assert response.json()["supplier_id"] == "SUP002"

# ============================================================
# TASK 4 — DISPUTE RESOLUTION SUGGESTIONS
# ============================================================


def seed_historical_match(
    match_id,
    supplier_id,
    invoice_number,
    discrepancies,
    resolution_reason,
):
    """
    Seed a previously resolved three-way-match record.

    These records represent historical disputes that were
    already resolved by a compliance officer.
    """

    three_way_matches[
        (supplier_id, invoice_number)
    ] = {
        "match_id": match_id,
        "supplier_id": supplier_id,
        "invoice_number": invoice_number,
        "status": "matched",
        "lines": [],
        "discrepancies": discrepancies,
        "created_at": None,
        "created_by": (
            "procurementmanager@company.com"
        ),
        "resolution": {
            "reason": resolution_reason,
            "resolved_at": None,
            "resolved_by": (
                "complianceofficer@company.com"
            ),
            "resolved_role": "compliance_officer",
        },
        "resolved_at": None,
        "resolved_by": (
            "complianceofficer@company.com"
        ),
        "payment_approved": False,
        "payment_approved_at": None,
        "payment_approved_by": None,
        "payment_approved_role": None,
    }


def create_price_discrepancy_match(
    procurement_client,
    invoice_number="INV1001",
):
    """
    Create a real current price-mismatch case through
    the existing three-way-match API.
    """

    prepare_exact_match(
        invoice_number=invoice_number,
    )

    invoices[
        ("SUP001", invoice_number)
    ]["items"][0]["unit_price"] = 106.0

    response = procurement_client.post(
        match_url(
            supplier_id="SUP001",
            invoice_number=invoice_number,
        )
    )

    assert response.status_code == 200
    assert response.json()["status"] == "discrepancy"

    return response


# ============================================================
# 47. PRICE MISMATCH RESOLUTION SUGGESTION
# ============================================================

def test_price_mismatch_resolution_suggestion(
    procurement_client,
    compliance_client,
):
    """
    Historical price mismatches mostly resulted in
    corrected invoices.

    The current price mismatch should therefore suggest
    correcting the invoice.
    """

    seed_historical_match(
        match_id="HIST-PRICE-001",
        supplier_id="SUP001",
        invoice_number="OLD-PRICE-001",
        discrepancies=["price_mismatch"],
        resolution_reason=(
            "Corrected invoice received from supplier."
        ),
    )

    seed_historical_match(
        match_id="HIST-PRICE-002",
        supplier_id="SUP002",
        invoice_number="OLD-PRICE-002",
        discrepancies=["price_mismatch"],
        resolution_reason=(
            "Invoice correction requested."
        ),
    )

    seed_historical_match(
        match_id="HIST-PRICE-003",
        supplier_id="SUP003",
        invoice_number="OLD-PRICE-003",
        discrepancies=["price_mismatch"],
        resolution_reason=(
            "Credit note issued."
        ),
    )

    create_price_discrepancy_match(
        procurement_client,
        invoice_number="INV1001",
    )

    response = compliance_client.get(
        resolution_suggestion_url(
            supplier_id="SUP001",
            invoice_number="INV1001",
        )
    )

    assert response.status_code == 200

    data = response.json()

    assert data["supplier_id"] == "SUP001"
    assert data["invoice_number"] == "INV1001"

    assert len(data["suggestions"]) == 1

    suggestion = data["suggestions"][0]

    assert suggestion["discrepancy_type"] == (
        "price_mismatch"
    )

    assert suggestion["suggested_action"] == (
        "correct_invoice"
    )

    assert suggestion["historical_case_count"] == 3
    assert suggestion["supporting_case_count"] == 2


# ============================================================
# 48. QUANTITY MISMATCH RESOLUTION SUGGESTION
# ============================================================

def test_quantity_mismatch_resolution_suggestion(
    procurement_client,
    compliance_client,
):
    """
    Historical quantity mismatches mostly resulted in
    credit notes.
    """

    seed_historical_match(
        match_id="HIST-QTY-001",
        supplier_id="SUP001",
        invoice_number="OLD-QTY-001",
        discrepancies=["quantity_mismatch"],
        resolution_reason=(
            "Credit note issued for excess quantity."
        ),
    )

    seed_historical_match(
        match_id="HIST-QTY-002",
        supplier_id="SUP002",
        invoice_number="OLD-QTY-002",
        discrepancies=["quantity_mismatch"],
        resolution_reason=(
            "Credit memo issued."
        ),
    )

    seed_historical_match(
        match_id="HIST-QTY-003",
        supplier_id="SUP003",
        invoice_number="OLD-QTY-003",
        discrepancies=["quantity_mismatch"],
        resolution_reason=(
            "Manual compliance review completed."
        ),
    )

    prepare_exact_match()

    invoices[
        ("SUP001", "INV1001")
    ]["items"][0]["quantity"] = 5

    match_response = procurement_client.post(
        match_url()
    )

    assert match_response.status_code == 200
    assert match_response.json()["status"] == (
        "discrepancy"
    )

    response = compliance_client.get(
        resolution_suggestion_url()
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data["suggestions"]) == 1

    suggestion = data["suggestions"][0]

    assert suggestion["discrepancy_type"] == (
        "quantity_mismatch"
    )

    assert suggestion["suggested_action"] == (
        "credit_note"
    )

    assert suggestion["historical_case_count"] == 3
    assert suggestion["supporting_case_count"] == 2


# ============================================================
# 49. MULTIPLE DISCREPANCIES GET MULTIPLE SUGGESTIONS
# ============================================================

def test_multiple_discrepancies_get_multiple_suggestions(
    procurement_client,
    compliance_client,
):
    """
    A dispute containing quantity + price mismatches
    should receive one suggestion for each discrepancy.
    """

    seed_historical_match(
        match_id="HIST-MULTI-001",
        supplier_id="SUP001",
        invoice_number="OLD-MULTI-001",
        discrepancies=["quantity_mismatch"],
        resolution_reason="Credit note issued.",
    )

    seed_historical_match(
        match_id="HIST-MULTI-002",
        supplier_id="SUP002",
        invoice_number="OLD-MULTI-002",
        discrepancies=["price_mismatch"],
        resolution_reason="Corrected invoice received.",
    )

    prepare_exact_match()

    invoice = invoices[
        ("SUP001", "INV1001")
    ]

    invoice["items"][0]["quantity"] = 5
    invoice["items"][0]["unit_price"] = 106.0

    match_response = procurement_client.post(
        match_url()
    )

    assert match_response.status_code == 200

    assert match_response.json()["status"] == (
        "discrepancy"
    )

    response = compliance_client.get(
        resolution_suggestion_url()
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data["suggestions"]) == 2

    suggestions = {
        item["discrepancy_type"]: item
        for item in data["suggestions"]
    }

    assert (
        suggestions["quantity_mismatch"][
            "suggested_action"
        ]
        == "credit_note"
    )

    assert (
        suggestions["price_mismatch"][
            "suggested_action"
        ]
        == "correct_invoice"
    )


# ============================================================
# 50. NO HISTORICAL EVIDENCE
# ============================================================

def test_no_historical_evidence_returns_no_suggestion(
    procurement_client,
    compliance_client,
):
    """
    The system must not invent a resolution suggestion
    when no historical resolved case exists.
    """

    create_price_discrepancy_match(
        procurement_client,
    )

    response = compliance_client.get(
        resolution_suggestion_url()
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data["suggestions"]) == 1

    suggestion = data["suggestions"][0]

    assert suggestion["discrepancy_type"] == (
        "price_mismatch"
    )

    assert suggestion["suggested_action"] is None

    assert suggestion["historical_case_count"] == 0

    assert suggestion["supporting_case_count"] == 0


# ============================================================
# 51. UNRESOLVED HISTORICAL CASE IS IGNORED
# ============================================================

def test_unresolved_historical_case_is_ignored(
    procurement_client,
    compliance_client,
):
    """
    A historical discrepancy that has not been resolved
    must not be used as resolution evidence.
    """

    three_way_matches[
        ("SUP001", "OLD-UNRESOLVED")
    ] = {
        "match_id": "HIST-UNRESOLVED-001",
        "supplier_id": "SUP001",
        "invoice_number": "OLD-UNRESOLVED",
        "status": "discrepancy",
        "lines": [],
        "discrepancies": ["price_mismatch"],
        "created_at": None,
        "created_by": (
            "procurementmanager@company.com"
        ),
        "resolution": None,
        "resolved_at": None,
        "resolved_by": None,
        "payment_approved": False,
        "payment_approved_at": None,
        "payment_approved_by": None,
        "payment_approved_role": None,
    }

    create_price_discrepancy_match(
        procurement_client,
    )

    response = compliance_client.get(
        resolution_suggestion_url()
    )

    assert response.status_code == 200

    data = response.json()

    suggestion = data["suggestions"][0]

    assert suggestion["suggested_action"] is None
    assert suggestion["historical_case_count"] == 0
    assert suggestion["supporting_case_count"] == 0


# ============================================================
# 52. CURRENT DISPUTE IS NOT USED AS HISTORY
# ============================================================

def test_current_dispute_is_not_used_as_history(
    procurement_client,
    compliance_client,
):
    """
    The current unresolved dispute must never count as
    its own historical evidence.
    """

    create_price_discrepancy_match(
        procurement_client,
    )

    current_match = three_way_matches[
        ("SUP001", "INV1001")
    ]

    # Add a resolution reason to the current record while
    # keeping the current status as discrepancy.
    current_match["resolution"] = {
        "reason": "Corrected invoice received.",
        "resolved_at": None,
        "resolved_by": None,
        "resolved_role": None,
    }

    response = compliance_client.get(
        resolution_suggestion_url()
    )

    assert response.status_code == 200

    data = response.json()

    suggestion = data["suggestions"][0]

    assert suggestion["suggested_action"] is None
    assert suggestion["historical_case_count"] == 0
    assert suggestion["supporting_case_count"] == 0


# ============================================================
# 53. SUGGESTION DOES NOT RESOLVE DISPUTE
# ============================================================

def test_suggestion_is_read_only(
    procurement_client,
    compliance_client,
):
    """
    Getting a suggestion must not change the discrepancy
    status or P2P state.
    """

    seed_historical_match(
        match_id="HIST-READONLY-001",
        supplier_id="SUP001",
        invoice_number="OLD-READONLY-001",
        discrepancies=["price_mismatch"],
        resolution_reason=(
            "Corrected invoice received."
        ),
    )

    create_price_discrepancy_match(
        procurement_client,
    )

    before_status = three_way_matches[
        ("SUP001", "INV1001")
    ]["status"]

    before_p2p_state = p2p_states["PO1001"]

    response = compliance_client.get(
        resolution_suggestion_url()
    )

    assert response.status_code == 200

    assert (
        three_way_matches[
            ("SUP001", "INV1001")
        ]["status"]
        == before_status
    )

    assert (
        p2p_states["PO1001"]
        == before_p2p_state
        == P2PState.discrepancy
    )


# ============================================================
# 54. SUPPLIER CANNOT GET RESOLUTION SUGGESTION
# ============================================================

def test_supplier_cannot_get_resolution_suggestion(
    procurement_client,
    supplier_client,
):
    """
    Resolution suggestions are intended for the
    compliance workflow.
    """

    create_price_discrepancy_match(
        procurement_client,
    )

    response = supplier_client.get(
        resolution_suggestion_url()
    )

    assert response.status_code == 403


# ============================================================
# 55. SUPPLIER CANNOT ACCESS OTHER SUPPLIER SUGGESTION
# ============================================================

def test_supplier_cannot_access_other_supplier_suggestion(
    procurement_client,
    supplier_client,
):
    """
    Supplier scoping must still apply to the new endpoint.
    """

    seed_historical_match(
        match_id="HIST-CROSS-001",
        supplier_id="SUP002",
        invoice_number="OLD-CROSS-001",
        discrepancies=["price_mismatch"],
        resolution_reason=(
            "Corrected invoice received."
        ),
    )

    # Build a SUP002 current discrepancy.
    prepare_exact_match(
        supplier_id="SUP002",
    )

    invoices[
        ("SUP002", "INV1001")
    ]["items"][0]["unit_price"] = 106.0

    response = procurement_client.post(
        match_url(
            supplier_id="SUP002",
            invoice_number="INV1001",
        )
    )

    assert response.status_code == 200
    assert response.json()["status"] == (
        "discrepancy"
    )

    # SUP001 supplier tries to access SUP002.
    response = supplier_client.get(
        resolution_suggestion_url(
            supplier_id="SUP002",
            invoice_number="INV1001",
        )
    )

    assert response.status_code == 403


# ============================================================
# 56. UNKNOWN MATCH RETURNS 404
# ============================================================

def test_unknown_resolution_suggestion_match_returns_404(
    compliance_client,
):
    response = compliance_client.get(
        resolution_suggestion_url(
            supplier_id="SUP001",
            invoice_number="INV-NOT-FOUND",
        )
    )

    assert response.status_code == 404

    assert "three-way match not found" in (
        response.text.lower()
    )


# ============================================================
# 57. MATCHED CASE CANNOT GENERATE SUGGESTION
# ============================================================

def test_matched_case_cannot_generate_resolution_suggestion(
    procurement_client,
    compliance_client,
):
    prepare_exact_match()

    response = procurement_client.post(
        match_url()
    )

    assert response.status_code == 200
    assert response.json()["status"] == "matched"

    response = compliance_client.get(
        resolution_suggestion_url()
    )

    assert response.status_code == 400

    assert "unresolved discrepancies" in (
        response.text.lower()
    )


