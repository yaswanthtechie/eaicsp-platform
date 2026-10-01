from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import verify_token
from app.schemas.goods_receipt import (
    GoodsReceiptCreate,
    GoodsReceiptResponse,
)
from app.services.goods_receipt_service import (
    create_goods_receipt,
    get_all_goods_receipts,
    get_goods_receipt_by_id,
    get_goods_receipts_by_po,
)
from app.services.purchase_order_service import (
    purchase_orders,
)


router = APIRouter()


# ============================================================
# CREATE GOODS RECEIPT
# ============================================================

@router.post(
    "/goods-receipts",
    response_model=GoodsReceiptResponse,
    status_code=201,
)
def create_goods_receipt_endpoint(
    receipt: GoodsReceiptCreate,
    user=Depends(verify_token),
):
    """
    Create a Goods Receipt.

    Goods Receipt creation is a warehouse-side activity and is
    restricted to the Warehouse Manager role.

    The authenticated user's email is used as created_by.
    The client cannot provide or override the actor identity.
    """

    role = user.get("role")

    # Goods Receipt is a warehouse-side activity.
    if role != "warehouse_manager":
        raise HTTPException(
            status_code=403,
            detail="Only Warehouse Manager can create Goods Receipts.",
        )

    email = user.get("email")

    if not email:
        raise HTTPException(
            status_code=403,
            detail="Authenticated user email is required.",
        )

    try:
        return create_goods_receipt(
            receipt=receipt,
            created_by=email,
        )

    except ValueError as exc:
        message = str(exc)

        if message == "Purchase Order not found.":
            raise HTTPException(
                status_code=404,
                detail=message,
            )

        raise HTTPException(
            status_code=400,
            detail=message,
        )


# ============================================================
# GET GOODS RECEIPT BY ID
# ============================================================

@router.get(
    "/goods-receipts/{receipt_id}",
    response_model=GoodsReceiptResponse,
)
def get_goods_receipt_endpoint(
    receipt_id: str,
    user=Depends(verify_token),
):
    """
    Get a Goods Receipt by ID.

    Supplier:
        - own receipt -> 200
        - another supplier's receipt -> 403
        - unknown receipt -> 403
        - missing supplier_id -> 403

    Internal authenticated users:
        - existing receipt -> 200
        - unknown receipt -> 404

    Supplier requests intentionally return a uniform 403 for
    inaccessible or unknown receipt IDs so that suppliers
    cannot determine whether another supplier's receipt exists.
    """

    role = user.get("role")

    # --------------------------------------------------------
    # SUPPLIER
    # --------------------------------------------------------

    if role == "supplier":

        supplier_id = user.get("supplier_id")

        # Supplier identity is mandatory.
        if not supplier_id:
            raise HTTPException(
                status_code=403,
                detail="Supplier identity is missing.",
            )

        receipt = get_goods_receipt_by_id(receipt_id)

        # Do not reveal whether the receipt exists.
        if not receipt:
            raise HTTPException(
                status_code=403,
                detail="Forbidden: goods receipt is not accessible.",
            )

        # Supplier may only access its own receipt.
        if receipt.get("supplier_id") != supplier_id:
            raise HTTPException(
                status_code=403,
                detail="Forbidden: supplier does not own this Goods Receipt.",
            )

        return receipt

    # --------------------------------------------------------
    # INTERNAL AUTHENTICATED USERS
    # --------------------------------------------------------

    receipt = get_goods_receipt_by_id(receipt_id)

    if not receipt:
        raise HTTPException(
            status_code=404,
            detail="Goods Receipt not found.",
        )

    return receipt


# ============================================================
# GET GOODS RECEIPTS FOR PURCHASE ORDER
# ============================================================

@router.get(
    "/purchase-orders/{po_number}/goods-receipts",
    response_model=list[GoodsReceiptResponse],
)
def get_goods_receipts_for_po(
    po_number: str,
    user=Depends(verify_token),
):
    """
    Get Goods Receipts associated with a Purchase Order.

    Supplier users:
        - can access only their own Purchase Order
        - cannot determine another supplier's PO receipt data
        - require supplier_id in the authenticated token

    Internal authenticated users:
        - can access receipts for any existing Purchase Order

    The Purchase Order is used as the authorization boundary
    before retrieving the associated Goods Receipts.
    """

    # --------------------------------------------------------
    # 1. PURCHASE ORDER MUST EXIST
    # --------------------------------------------------------

    po = purchase_orders.get(po_number)

    if not po:
        raise HTTPException(
            status_code=404,
            detail="Purchase Order not found.",
        )

    role = user.get("role")

    # --------------------------------------------------------
    # 2. SUPPLIER OWNERSHIP
    # --------------------------------------------------------

    if role == "supplier":

        supplier_id = user.get("supplier_id")

        if not supplier_id:
            raise HTTPException(
                status_code=403,
                detail="Supplier identity is missing.",
            )

        if po.get("supplier_id") != supplier_id:
            raise HTTPException(
                status_code=403,
                detail="Supplier does not own this Purchase Order.",
            )

    # --------------------------------------------------------
    # 3. GET RECEIPTS
    # --------------------------------------------------------

    receipts = get_goods_receipts_by_po(po_number)

    # --------------------------------------------------------
    # 4. DEFENSIVE SUPPLIER FILTER
    # --------------------------------------------------------

    if role == "supplier":
        return [
            receipt
            for receipt in receipts
            if receipt.get("supplier_id") == supplier_id
        ]

    # --------------------------------------------------------
    # 5. INTERNAL USERS
    # --------------------------------------------------------

    return receipts


# ============================================================
# GET ALL GOODS RECEIPTS
# ============================================================

@router.get(
    "/goods-receipts",
    response_model=list[GoodsReceiptResponse],
)
def get_goods_receipts(
    user=Depends(verify_token),
):
    """
    Get Goods Receipts.

    Supplier users receive only receipts belonging to their
    authenticated supplier_id.

    Internal authenticated users receive all Goods Receipts.
    """

    receipts = get_all_goods_receipts()

    role = user.get("role")

    # --------------------------------------------------------
    # SUPPLIER SCOPING
    # --------------------------------------------------------

    if role == "supplier":

        supplier_id = user.get("supplier_id")

        if not supplier_id:
            raise HTTPException(
                status_code=403,
                detail="Supplier identity is missing.",
            )

        return [
            receipt
            for receipt in receipts
            if receipt.get("supplier_id") == supplier_id
        ]

    # --------------------------------------------------------
    # INTERNAL AUTHENTICATED USERS
    # --------------------------------------------------------

    return receipts