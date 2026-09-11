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

    For the current Milestone 1 implementation,
    the Goods Receipt must contain the complete quantity
    ordered in the Purchase Order.
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
    # 7. Validate all PO items are present
    #
    # Current Milestone 1 rule:
    # Goods Receipt must represent the complete PO quantity.
    # ---------------------------------------------------------

    missing_items = set(po_items) - set(receipt_items)

    if missing_items:
        missing = ", ".join(sorted(missing_items))

        raise ValueError(
            "Goods Receipt must contain all Purchase Order "
            f"items. Missing item(s): {missing}."
        )

    # ---------------------------------------------------------
    # 8. Validate no extra items are present
    # ---------------------------------------------------------

    extra_items = set(receipt_items) - set(po_items)

    if extra_items:
        extra = ", ".join(sorted(extra_items))

        raise ValueError(
            "Goods Receipt contains item(s) that do not "
            f"exist in the Purchase Order: {extra}."
        )

    # ---------------------------------------------------------
    # 9. Validate received quantity
    #
    # Each received quantity must exactly match the
    # corresponding PO quantity.
    # ---------------------------------------------------------

    for item_code, ordered_quantity in po_items.items():

        received_quantity = receipt_items[item_code]

        if received_quantity > ordered_quantity:
            raise ValueError(
                f"Received quantity for item "
                f"'{item_code}' exceeds the Purchase Order "
                f"quantity. Ordered: {ordered_quantity}, "
                f"Received: {received_quantity}."
            )

        if received_quantity < ordered_quantity:
            raise ValueError(
                f"Goods Receipt is incomplete for item "
                f"'{item_code}'. Ordered: {ordered_quantity}, "
                f"Received: {received_quantity}."
            )

    # ---------------------------------------------------------
    # 10. Generate receipt ID
    # ---------------------------------------------------------

    receipt_id = (
        f"GR-{uuid4().hex[:12].upper()}"
    )

    # ---------------------------------------------------------
    # 11. Build Goods Receipt record
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
    # 12. Store Goods Receipt
    # ---------------------------------------------------------

    goods_receipts[receipt_id] = receipt_data

    # ---------------------------------------------------------
    # 13. Advance P2P state
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
    # 14. Fulfill the Purchase Order
    #
    # Since the complete PO quantity has now been received:
    #
    #     acknowledged -> fulfilled
    #
    # IMPORTANT:
    # This is PO status, NOT P2P state.
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

