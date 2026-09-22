from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.goods_receipt import (
    GoodsReceiptCreate,
    GoodsReceiptStatus,
)

from app.schemas.purchase_order import PurchaseOrderStatus

from app.services.po_p2p_state_machine import (
    P2PState,
    get_p2p_state,
    transition_p2p,
)

from app.services.purchase_order_service import (
    get_purchase_order_by_id,
    transition_purchase_order,
)


goods_receipts: dict[str, dict] = {}


def create_goods_receipt(
    receipt: GoodsReceiptCreate,
    created_by: str,
):
    """
    Create a Goods Receipt for a Purchase Order.

    Goods Receipt is created by an internal Warehouse Manager.

    The supplier_id is derived from the Purchase Order instead
    of the authenticated user's supplier_id.

    P2P transition:
        shipped -> received

    PO transition:
        acknowledged -> fulfilled

    Partial receipts are allowed. Received quantity must be
    greater than zero and must not exceed the Purchase Order
    quantity.

    Quantity differences are handled by the three-way match
    service and flagged as discrepancies for human review.
    """

    # ---------------------------------------------------------
    # 1. Verify Purchase Order exists
    # ---------------------------------------------------------

    purchase_order = get_purchase_order_by_id(
        receipt.po_number
    )

    if not purchase_order:
        raise ValueError(
            "Purchase Order not found."
        )

    # ---------------------------------------------------------
    # 2. Get supplier from the Purchase Order
    #
    # Warehouse Manager is an internal user and normally does
    # not have a supplier_id in the authentication token.
    #
    # Therefore supplier ownership comes from the PO itself.
    # ---------------------------------------------------------

    supplier_id = purchase_order["supplier_id"]

    # ---------------------------------------------------------
    # 3. Validate existing PO lifecycle
    #
    # The PO must be acknowledged before the Goods Receipt.
    #
    # The P2P state-machine check below additionally requires:
    #
    #     shipped -> received
    # ---------------------------------------------------------

    if purchase_order["status"] != PurchaseOrderStatus.acknowledged:
        raise ValueError(
            "Goods Receipt can be created only for an "
            "acknowledged Purchase Order."
        )

    # ---------------------------------------------------------
    # 4. Validate shared P2P state
    #
    # Only:
    #
    #     shipped -> received
    #
    # is allowed.
    # ---------------------------------------------------------

    current_p2p_state = get_p2p_state(
        receipt.po_number
    )

    if current_p2p_state != P2PState.shipped:
        raise ValueError(
            "Goods Receipt can be created only when the "
            "Purchase Order is in the shipped P2P state."
        )

    # ---------------------------------------------------------
    # 5. Validate received items against PO items
    # ---------------------------------------------------------

    po_items = {
        item["item_code"]: item["quantity"]
        for item in purchase_order["items"]
    }

    receipt_items = {
        item.item_code: item.quantity
        for item in receipt.items
    }

    # ---------------------------------------------------------
    # 6. Validate duplicate receipt item codes
    # ---------------------------------------------------------

    if len(receipt_items) != len(receipt.items):
        raise ValueError(
            "Duplicate goods receipt item."
        )

    # ---------------------------------------------------------
    # 7. Validate no extra items are present
    # ---------------------------------------------------------

    extra_items = set(receipt_items) - set(po_items)

    if extra_items:
        extra = ", ".join(sorted(extra_items))

        raise ValueError(
            "Goods Receipt contains item(s) that do not "
            f"exist in the Purchase Order: {extra}."
        )

    # ---------------------------------------------------------
    # 8. Validate received quantity
    #
    # Partial receipts are allowed.
    #
    # Reject only:
    #   - zero/negative quantity
    #   - quantity greater than PO quantity
    #
    # A quantity lower than the PO quantity is allowed so
    # that the three-way match can flag it as a discrepancy.
    # ---------------------------------------------------------

    for item_code, received_quantity in receipt_items.items():

        ordered_quantity = po_items[item_code]

        if received_quantity <= 0:
            raise ValueError(
                f"Received quantity for item "
                f"'{item_code}' must be greater than zero."
            )

        if received_quantity > ordered_quantity:
            raise ValueError(
                f"Received quantity for item "
                f"'{item_code}' exceeds the Purchase Order "
                f"quantity. Ordered: {ordered_quantity}, "
                f"Received: {received_quantity}."
            )

    # ---------------------------------------------------------
    # 9. Generate receipt ID
    # ---------------------------------------------------------

    receipt_id = (
        f"GR-{uuid4().hex[:12].upper()}"
    )

    # ---------------------------------------------------------
    # 10. Build Goods Receipt record
    # ---------------------------------------------------------

    receipt_data = {
        "receipt_id": receipt_id,
        "po_number": receipt.po_number,
        "supplier_id": supplier_id,
        "receipt_date": receipt.receipt_date,
        "warehouse": receipt.warehouse,
        "received_by": receipt.received_by,
        "items": [
            item.model_dump()
            for item in receipt.items
        ],
        "status": GoodsReceiptStatus.received,
        "created_at": datetime.now(timezone.utc),
        "created_by": created_by,
    }

    # ---------------------------------------------------------
    # 11. Store Goods Receipt
    # ---------------------------------------------------------

    goods_receipts[receipt_id] = receipt_data

    # ---------------------------------------------------------
    # 12. Advance P2P state
    #
    #     shipped -> received
    # ---------------------------------------------------------

    try:

        transition_p2p(
            receipt.po_number,
            P2PState.received,
        )

    except ValueError:

        # Roll back Goods Receipt if P2P transition fails
        del goods_receipts[receipt_id]

        raise

    # ---------------------------------------------------------
    # 13. Fulfill the Purchase Order
    #
    # IMPORTANT:
    # This is PO status, NOT P2P state.
    #
    # The existing Milestone 1 flow requires the PO to move
    # from acknowledged -> fulfilled after Goods Receipt.
    # ---------------------------------------------------------

    try:

        transition_purchase_order(
            po_number=receipt.po_number,
            actor=created_by,
            target_state=PurchaseOrderStatus.fulfilled,
        )

    except ValueError:

        # Roll back P2P state
        # received -> shipped
        #
        # We directly restore the previous state because
        # the shared state machine intentionally does not
        # allow a normal received -> shipped transition.

        from app.services.po_p2p_state_machine import p2p_states

        p2p_states[receipt.po_number] = (
            P2PState.shipped
        )

        # Roll back Goods Receipt
        del goods_receipts[receipt_id]

        raise

    return receipt_data


def get_goods_receipt_by_id(receipt_id: str):
    """
    Get a Goods Receipt by receipt ID.
    """

    return goods_receipts.get(receipt_id)


def get_goods_receipts_by_po(po_number: str):
    """
    Get all Goods Receipts for a Purchase Order.
    """

    return [
        receipt
        for receipt in goods_receipts.values()
        if receipt["po_number"] == po_number
    ]


def get_all_goods_receipts():
    """
    Return all Goods Receipts.
    """

    return list(goods_receipts.values())

