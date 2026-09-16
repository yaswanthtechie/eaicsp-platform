import pytest

from app.schemas.goods_receipt import GoodsReceiptCreate
from app.schemas.purchase_order import PurchaseOrderStatus

from app.services.goods_receipt_service import (
    create_goods_receipt,
    get_all_goods_receipts,
    get_goods_receipt_by_id,
    get_goods_receipts_by_po,
    goods_receipts,
)

from app.services.po_p2p_state_machine import (
    P2PState,
    initialize_p2p_state,
    p2p_states,
)

from app.services.purchase_order_service import (
    purchase_orders,
)


# ============================================================
# TEST FIXTURE
# ============================================================


@pytest.fixture(autouse=True)
def clear_test_data():
    """
    Clear all in-memory test data before and after every test.
    """

    goods_receipts.clear()
    purchase_orders.clear()
    p2p_states.clear()

    yield

    goods_receipts.clear()
    purchase_orders.clear()
    p2p_states.clear()


# ============================================================
# TEST DATA HELPERS
# ============================================================


def create_shipped_po(
    po_number="PO1001",
    supplier_id="SUP001",
):
    """
    Create a PO that is ready for Goods Receipt.

    PO business status:
        acknowledged

    P2P workflow state:
        shipped

    Expected next P2P transition:
        shipped -> received
    """

    purchase_orders[po_number] = {
        "po_number": po_number,
        "supplier_id": supplier_id,
        "items": [
            {
                "item_code": "LAP001",
                "description": "Laptop",
                "quantity": 10,
                "unit_price": 50000.0,
            },
            {
                "item_code": "MOU001",
                "description": "Mouse",
                "quantity": 10,
                "unit_price": 1500.0,
            },
        ],
        "total_amount": 515000.0,
        "status": PurchaseOrderStatus.acknowledged,
        "created_at": "2026-09-09T08:00:00",
        "expected_delivery": "2026-09-15",
        "actual_delivery_date": None,
        "history": [],
    }

    initialize_p2p_state(
        po_number,
        P2PState.shipped,
    )


def valid_goods_receipt(
    po_number="PO1001",
    quantity_lap=10,
    quantity_mouse=10,
):
    """
    Create a valid Goods Receipt payload.
    """

    return GoodsReceiptCreate(
        po_number=po_number,
        receipt_date="2026-09-09",
        warehouse="WH-HYD-01",
        received_by="warehouse.user@company.com",
        items=[
            {
                "item_code": "LAP001",
                "quantity": quantity_lap,
            },
            {
                "item_code": "MOU001",
                "quantity": quantity_mouse,
            },
        ],
    )


def create_goods_receipt_for_supplier(
    supplier_id="SUP001",
    po_number="PO1001",
    quantity_lap=10,
    quantity_mouse=10,
    created_by="warehouse.user@company.com",
):
    """
    Create a shipped PO for the requested supplier and then
    create a Goods Receipt through the service layer.

    This helper is used by API scoping tests.
    """

    create_shipped_po(
        po_number=po_number,
        supplier_id=supplier_id,
    )

    receipt = create_goods_receipt(
        valid_goods_receipt(
            po_number=po_number,
            quantity_lap=quantity_lap,
            quantity_mouse=quantity_mouse,
        ),
        created_by=created_by,
    )

    return receipt


# ============================================================
# SUCCESS CASES
# ============================================================


def test_create_goods_receipt_successfully():
    create_shipped_po()

    receipt = create_goods_receipt(
        valid_goods_receipt(),
        created_by="warehouse.user@company.com",
    )

    assert receipt["receipt_id"].startswith("GR-")
    assert receipt["po_number"] == "PO1001"

    # Supplier ID must come from the Purchase Order.
    assert receipt["supplier_id"] == "SUP001"

    assert receipt["warehouse"] == "WH-HYD-01"
    assert (
        receipt["received_by"]
        == "warehouse.user@company.com"
    )
    assert receipt["status"] == "received"


def test_goods_receipt_gets_supplier_id_from_purchase_order():
    create_shipped_po()

    receipt = create_goods_receipt(
        valid_goods_receipt(),
        created_by="warehouse.user@company.com",
    )

    assert (
        receipt["supplier_id"]
        == purchase_orders["PO1001"]["supplier_id"]
    )


def test_goods_receipt_created_by_warehouse_manager():
    create_shipped_po()

    receipt = create_goods_receipt(
        valid_goods_receipt(),
        created_by="warehouse.manager@company.com",
    )

    assert (
        receipt["created_by"]
        == "warehouse.manager@company.com"
    )


def test_goods_receipt_moves_p2p_state_to_received():
    create_shipped_po()

    create_goods_receipt(
        valid_goods_receipt(),
        created_by="warehouse.user@company.com",
    )

    assert (
        p2p_states["PO1001"]
        == P2PState.received
    )


def test_goods_receipt_fulfills_purchase_order():
    create_shipped_po()

    create_goods_receipt(
        valid_goods_receipt(),
        created_by="warehouse.user@company.com",
    )

    assert (
        purchase_orders["PO1001"]["status"]
        == PurchaseOrderStatus.fulfilled
    )


def test_goods_receipt_sets_actual_delivery_date():
    create_shipped_po()

    create_goods_receipt(
        valid_goods_receipt(),
        created_by="warehouse.user@company.com",
    )

    assert (
        purchase_orders["PO1001"]["actual_delivery_date"]
        is not None
    )


def test_goods_receipt_creates_fulfillment_history_event():
    create_shipped_po()

    create_goods_receipt(
        valid_goods_receipt(),
        created_by="warehouse.user@company.com",
    )

    history = purchase_orders["PO1001"]["history"]

    assert history

    event = history[-1]

    assert event["po_number"] == "PO1001"
    assert event["supplier_id"] == "SUP001"

    assert (
        event["actor"]
        == "warehouse.user@company.com"
    )

    assert (
        event["from_status"]
        == PurchaseOrderStatus.acknowledged
    )

    assert (
        event["to_status"]
        == PurchaseOrderStatus.fulfilled
    )


def test_goods_receipt_is_stored():
    create_shipped_po()

    receipt = create_goods_receipt(
        valid_goods_receipt(),
        created_by="warehouse.user@company.com",
    )

    assert receipt["receipt_id"] in goods_receipts
    assert goods_receipts[receipt["receipt_id"]] == receipt


def test_get_goods_receipt_by_id():
    create_shipped_po()

    receipt = create_goods_receipt(
        valid_goods_receipt(),
        created_by="warehouse.user@company.com",
    )

    result = get_goods_receipt_by_id(
        receipt["receipt_id"]
    )

    assert result == receipt


def test_get_goods_receipts_by_po():
    create_shipped_po()

    receipt = create_goods_receipt(
        valid_goods_receipt(),
        created_by="warehouse.user@company.com",
    )

    result = get_goods_receipts_by_po("PO1001")

    assert len(result) == 1

    assert (
        result[0]["receipt_id"]
        == receipt["receipt_id"]
    )


def test_get_all_goods_receipts():
    create_shipped_po()

    receipt = create_goods_receipt(
        valid_goods_receipt(),
        created_by="warehouse.user@company.com",
    )

    result = get_all_goods_receipts()

    assert len(result) == 1

    assert (
        result[0]["receipt_id"]
        == receipt["receipt_id"]
    )


# ============================================================
# NEGATIVE / BUSINESS RULE CASES
# ============================================================


def test_goods_receipt_for_nonexistent_po_is_rejected():
    receipt = valid_goods_receipt()

    with pytest.raises(
        ValueError,
        match="Purchase Order not found",
    ):
        create_goods_receipt(
            receipt,
            created_by="warehouse.user@company.com",
        )

    assert goods_receipts == {}


def test_goods_receipt_before_shipment_is_rejected():
    create_shipped_po()

    p2p_states["PO1001"] = P2PState.acknowledged

    with pytest.raises(
        ValueError,
        match="shipped P2P state",
    ):
        create_goods_receipt(
            valid_goods_receipt(),
            created_by="warehouse.user@company.com",
        )

    assert (
        p2p_states["PO1001"]
        == P2PState.acknowledged
    )

    assert (
        purchase_orders["PO1001"]["status"]
        == PurchaseOrderStatus.acknowledged
    )


def test_goods_receipt_after_receipt_is_rejected():
    create_shipped_po()

    # First Goods Receipt succeeds.
    create_goods_receipt(
        valid_goods_receipt(),
        created_by="warehouse.user@company.com",
    )

    # Second Goods Receipt must fail because:
    #
    # PO status = fulfilled
    # P2P state = received

    with pytest.raises(
        ValueError,
        match="acknowledged Purchase Order",
    ):
        create_goods_receipt(
            valid_goods_receipt(),
            created_by="warehouse.user@company.com",
        )

    assert (
        p2p_states["PO1001"]
        == P2PState.received
    )

    assert (
        purchase_orders["PO1001"]["status"]
        == PurchaseOrderStatus.fulfilled
    )


def test_goods_receipt_requires_shipped_p2p_state():
    create_shipped_po()

    invalid_states = [
        P2PState.acknowledged,
        P2PState.received,
        P2PState.invoiced,
        P2PState.matched,
        P2PState.discrepancy,
        P2PState.payment_approved,
    ]

    for state in invalid_states:

        p2p_states["PO1001"] = state

        with pytest.raises(
            ValueError,
            match="shipped P2P state",
        ):
            create_goods_receipt(
                valid_goods_receipt(),
                created_by="warehouse.user@company.com",
            )

        assert (
            p2p_states["PO1001"]
            == state
        )


def test_goods_receipt_with_unknown_item_is_rejected():
    create_shipped_po()

    receipt = GoodsReceiptCreate(
        po_number="PO1001",
        receipt_date="2026-09-09",
        warehouse="WH-HYD-01",
        received_by="warehouse.user@company.com",
        items=[
            {
                "item_code": "LAP001",
                "quantity": 10,
            },
            {
                "item_code": "MOU001",
                "quantity": 10,
            },
            {
                "item_code": "UNKNOWN",
                "quantity": 5,
            },
        ],
    )

    with pytest.raises(
        ValueError,
        match="do not exist in the Purchase Order",
    ):
        create_goods_receipt(
            receipt,
            created_by="warehouse.user@company.com",
        )

    assert goods_receipts == {}

    assert (
        p2p_states["PO1001"]
        == P2PState.shipped
    )

    assert (
        purchase_orders["PO1001"]["status"]
        == PurchaseOrderStatus.acknowledged
    )


def test_goods_receipt_quantity_cannot_exceed_po_quantity():
    create_shipped_po()

    receipt = GoodsReceiptCreate(
        po_number="PO1001",
        receipt_date="2026-09-09",
        warehouse="WH-HYD-01",
        received_by="warehouse.user@company.com",
        items=[
            {
                "item_code": "LAP001",
                "quantity": 11,
            },
            {
                "item_code": "MOU001",
                "quantity": 10,
            },
        ],
    )

    with pytest.raises(
        ValueError,
        match="exceeds the Purchase Order quantity",
    ):
        create_goods_receipt(
            receipt,
            created_by="warehouse.user@company.com",
        )

    assert goods_receipts == {}

    assert (
        p2p_states["PO1001"]
        == P2PState.shipped
    )


def test_goods_receipt_allows_partial_quantity():
    create_shipped_po()

    receipt = GoodsReceiptCreate(
        po_number="PO1001",
        receipt_date="2026-09-09",
        warehouse="WH-HYD-01",
        received_by="warehouse.user@company.com",
        items=[
            {
                "item_code": "LAP001",
                "quantity": 5,
            },
            {
                "item_code": "MOU001",
                "quantity": 10,
            },
        ],
    )

    result = create_goods_receipt(
        receipt,
        created_by="warehouse.user@company.com",
    )

    assert result["po_number"] == "PO1001"
    assert result["supplier_id"] == "SUP001"
    assert result["status"] == "received"

    assert result["items"][0]["quantity"] == 5
    assert result["items"][1]["quantity"] == 10

    assert result["receipt_id"] in goods_receipts

    assert (
        p2p_states["PO1001"]
        == P2PState.received
    )

    assert (
        purchase_orders["PO1001"]["status"]
        == PurchaseOrderStatus.fulfilled
    )


def test_goods_receipt_allows_missing_po_item_for_partial_receipt():
    create_shipped_po()

    receipt = GoodsReceiptCreate(
        po_number="PO1001",
        receipt_date="2026-09-09",
        warehouse="WH-HYD-01",
        received_by="warehouse.user@company.com",
        items=[
            {
                "item_code": "LAP001",
                "quantity": 10,
            }
        ],
    )

    result = create_goods_receipt(
        receipt,
        created_by="warehouse.user@company.com",
    )

    assert result["po_number"] == "PO1001"
    assert result["supplier_id"] == "SUP001"
    assert result["status"] == "received"

    assert len(result["items"]) == 1
    assert result["items"][0]["item_code"] == "LAP001"
    assert result["items"][0]["quantity"] == 10

    assert result["receipt_id"] in goods_receipts

    assert (
        p2p_states["PO1001"]
        == P2PState.received
    )

    assert (
        purchase_orders["PO1001"]["status"]
        == PurchaseOrderStatus.fulfilled
    )


def test_duplicate_goods_receipt_item_is_rejected():
    create_shipped_po()

    receipt = GoodsReceiptCreate(
        po_number="PO1001",
        receipt_date="2026-09-09",
        warehouse="WH-HYD-01",
        received_by="warehouse.user@company.com",
        items=[
            {
                "item_code": "LAP001",
                "quantity": 5,
            },
            {
                "item_code": "LAP001",
                "quantity": 5,
            },
        ],
    )

    with pytest.raises(
        ValueError,
        match="Duplicate goods receipt item",
    ):
        create_goods_receipt(
            receipt,
            created_by="warehouse.user@company.com",
        )

    assert goods_receipts == {}

    assert (
        p2p_states["PO1001"]
        == P2PState.shipped
    )


# ============================================================
# P2P TRANSITION INTEGRITY
# ============================================================


def test_goods_receipt_does_not_allow_direct_acknowledged_to_received():
    create_shipped_po()

    p2p_states["PO1001"] = P2PState.acknowledged

    with pytest.raises(
        ValueError,
        match="shipped P2P state",
    ):
        create_goods_receipt(
            valid_goods_receipt(),
            created_by="warehouse.user@company.com",
        )

    assert (
        p2p_states["PO1001"]
        == P2PState.acknowledged
    )

    assert (
        purchase_orders["PO1001"]["status"]
        == PurchaseOrderStatus.acknowledged
    )

    assert goods_receipts == {}


def test_goods_receipt_transition_is_exactly_shipped_to_received():
    create_shipped_po()

    assert (
        p2p_states["PO1001"]
        == P2PState.shipped
    )

    create_goods_receipt(
        valid_goods_receipt(),
        created_by="warehouse.user@company.com",
    )

    assert (
        p2p_states["PO1001"]
        == P2PState.received
    )

    assert (
        p2p_states["PO1001"]
        != P2PState.invoiced
    )

    assert (
        p2p_states["PO1001"]
        != P2PState.matched
    )

    assert (
        p2p_states["PO1001"]
        != P2PState.payment_approved
    )


def test_goods_receipt_failure_does_not_store_receipt():
    create_shipped_po()

    receipt = GoodsReceiptCreate(
        po_number="PO1001",
        receipt_date="2026-09-09",
        warehouse="WH-HYD-01",
        received_by="warehouse.user@company.com",
        items=[
            {
                "item_code": "UNKNOWN",
                "quantity": 5,
            }
        ],
    )

    with pytest.raises(ValueError):
        create_goods_receipt(
            receipt,
            created_by="warehouse.user@company.com",
        )

    assert goods_receipts == {}

    assert (
        p2p_states["PO1001"]
        == P2PState.shipped
    )

    assert (
        purchase_orders["PO1001"]["status"]
        == PurchaseOrderStatus.acknowledged
    )


# ============================================================
# SCHEMA VALIDATION
# ============================================================


def test_goods_receipt_requires_at_least_one_item():
    with pytest.raises(ValueError):
        GoodsReceiptCreate(
            po_number="PO1001",
            receipt_date="2026-09-09",
            warehouse="WH-HYD-01",
            received_by="warehouse.user@company.com",
            items=[],
        )


def test_goods_receipt_quantity_must_be_positive():
    with pytest.raises(ValueError):
        GoodsReceiptCreate(
            po_number="PO1001",
            receipt_date="2026-09-09",
            warehouse="WH-HYD-01",
            received_by="warehouse.user@company.com",
            items=[
                {
                    "item_code": "LAP001",
                    "quantity": 0,
                }
            ],
        )


def test_goods_receipt_item_code_format_is_validated():
    with pytest.raises(ValueError):
        GoodsReceiptCreate(
            po_number="PO1001",
            receipt_date="2026-09-09",
            warehouse="WH-HYD-01",
            received_by="warehouse.user@company.com",
            items=[
                {
                    "item_code": "LAP 001",
                    "quantity": 5,
                }
            ],
        )


def test_goods_receipt_po_number_format_is_validated():
    with pytest.raises(ValueError):
        GoodsReceiptCreate(
            po_number="PO 1001",
            receipt_date="2026-09-09",
            warehouse="WH-HYD-01",
            received_by="warehouse.user@company.com",
            items=[
                {
                    "item_code": "LAP001",
                    "quantity": 5,
                }
            ],
        )


def test_goods_receipt_requires_acknowledged_purchase_order():
    create_shipped_po()

    purchase_orders["PO1001"]["status"] = (
        PurchaseOrderStatus.draft
    )

    with pytest.raises(
        ValueError,
        match="acknowledged Purchase Order",
    ):
        create_goods_receipt(
            valid_goods_receipt(),
            created_by="warehouse.user@company.com",
        )

    assert goods_receipts == {}

    assert (
        p2p_states["PO1001"]
        == P2PState.shipped
    )

    assert (
        purchase_orders["PO1001"]["status"]
        == PurchaseOrderStatus.draft
    )


def test_goods_receipt_with_extra_item_is_rejected():
    create_shipped_po()

    receipt = GoodsReceiptCreate(
        po_number="PO1001",
        receipt_date="2026-09-09",
        warehouse="WH-HYD-01",
        received_by="warehouse.user@company.com",
        items=[
            {
                "item_code": "LAP001",
                "quantity": 10,
            },
            {
                "item_code": "MOU001",
                "quantity": 10,
            },
            {
                "item_code": "EXTRA001",
                "quantity": 1,
            },
        ],
    )

    with pytest.raises(
        ValueError,
        match="do not exist in the Purchase Order",
    ):
        create_goods_receipt(
            receipt,
            created_by="warehouse.user@company.com",
        )

    assert goods_receipts == {}

    assert (
        p2p_states["PO1001"]
        == P2PState.shipped
    )

    assert (
        purchase_orders["PO1001"]["status"]
        == PurchaseOrderStatus.acknowledged
    )


# ============================================================
# API SECURITY / SUPPLIER SCOPING
# ============================================================


def test_supplier_can_view_own_goods_receipt(
    supplier_client,
):
    """
    Supplier can retrieve its own Goods Receipt.
    """

    receipt = create_goods_receipt_for_supplier(
        supplier_id="SUP001",
    )

    response = supplier_client.get(
        f"/api/v1/goods-receipts/{receipt['receipt_id']}"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["receipt_id"] == receipt["receipt_id"]
    assert body["supplier_id"] == "SUP001"


def test_supplier_cannot_view_another_suppliers_goods_receipt(
    supplier_client,
):
    """
    Supplier SUP001 must not access a Goods Receipt
    belonging to SUP002.
    """

    receipt = create_goods_receipt_for_supplier(
        supplier_id="SUP002",
        po_number="PO2001",
    )

    response = supplier_client.get(
        f"/api/v1/goods-receipts/{receipt['receipt_id']}"
    )

    assert response.status_code == 403

    assert (
        "forbidden"
        in response.json()["detail"].lower()
    )


def test_supplier_cannot_determine_unknown_goods_receipt_existence(
    supplier_client,
):
    """
    Unknown Goods Receipt IDs must return the same forbidden
    response class used for inaccessible receipts.

    This prevents supplier users from determining whether
    another supplier's receipt exists.
    """

    response = supplier_client.get(
        "/api/v1/goods-receipts/GR-DOES-NOT-EXIST"
    )

    assert response.status_code == 403

    assert (
        "goods receipt is not accessible"
        in response.json()["detail"].lower()
    )


def test_supplier_gets_same_forbidden_response_for_existing_and_unknown_receipts(
    supplier_client,
):
    """
    Existing cross-supplier and unknown Goods Receipt IDs must
    both remain forbidden to supplier users.

    The exact detail text may differ, but both must remain 403.
    """

    receipt = create_goods_receipt_for_supplier(
        supplier_id="SUP002",
        po_number="PO2002",
    )

    existing_response = supplier_client.get(
        f"/api/v1/goods-receipts/{receipt['receipt_id']}"
    )

    unknown_response = supplier_client.get(
        "/api/v1/goods-receipts/GR-UNKNOWN"
    )

    assert existing_response.status_code == 403
    assert unknown_response.status_code == 403


def test_supplier_without_supplier_id_cannot_view_goods_receipt(
    supplier_no_id_client,
):
    """
    A supplier without supplier_id cannot access Goods Receipt data.
    """

    response = supplier_no_id_client.get(
        "/api/v1/goods-receipts/GR-DOES-NOT-EXIST"
    )

    assert response.status_code == 403

    assert (
        "supplier identity is missing"
        in response.json()["detail"].lower()
    )


def test_internal_user_gets_404_for_unknown_goods_receipt(
    procurement_client,
):
    """
    Internal authenticated users receive 404 for a genuinely
    unknown Goods Receipt.
    """

    response = procurement_client.get(
        "/api/v1/goods-receipts/GR-DOES-NOT-EXIST"
    )

    assert response.status_code == 404

    assert (
        "goods receipt not found"
        in response.json()["detail"].lower()
    )


def test_internal_user_can_view_existing_supplier_goods_receipt(
    procurement_client,
):
    """
    Internal authenticated users can view an existing Goods Receipt
    regardless of supplier ownership.
    """

    receipt = create_goods_receipt_for_supplier(
        supplier_id="SUP002",
        po_number="PO2003",
    )

    response = procurement_client.get(
        f"/api/v1/goods-receipts/{receipt['receipt_id']}"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["receipt_id"] == receipt["receipt_id"]
    assert body["supplier_id"] == "SUP002"

