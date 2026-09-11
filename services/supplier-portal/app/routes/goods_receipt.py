from fastapi import APIRouter, Depends, HTTPException, Request

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
    request: Request,
    user=Depends(verify_token),
):
    role = request.state.role

    # Goods Receipt is a warehouse-side activity.
    if role != "warehouse_manager":
        raise HTTPException(
            status_code=403,
            detail="Only Warehouse Manager can create Goods Receipts.",
        )

    email = request.state.email

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
    request: Request,
    user=Depends(verify_token),
):
    receipt = get_goods_receipt_by_id(receipt_id)

    # Unknown resource -> 404
    if not receipt:
        raise HTTPException(
            status_code=404,
            detail="Goods Receipt not found.",
        )

    role = request.state.role

    # --------------------------------------------------------
    # SUPPLIER SCOPING
    # --------------------------------------------------------

    if role == "supplier":

        supplier_id = request.state.supplier_id

        # Supplier identity is mandatory.
        if not supplier_id:
            raise HTTPException(
                status_code=403,
                detail="Supplier identity is missing.",
            )

        # Supplier may only access its own receipt.
        if receipt["supplier_id"] != supplier_id:
            raise HTTPException(
                status_code=403,
                detail="Supplier does not own this Goods Receipt.",
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
    request: Request,
    user=Depends(verify_token),
):
    # --------------------------------------------------------
    # 1. PURCHASE ORDER MUST EXIST
    # --------------------------------------------------------

    po = purchase_orders.get(po_number)

    if not po:
        raise HTTPException(
            status_code=404,
            detail="Purchase Order not found.",
        )

    role = request.state.role

    # --------------------------------------------------------
    # 2. SUPPLIER OWNERSHIP MUST BE CHECKED AGAINST THE PO
    # --------------------------------------------------------
    # Do this before looking at receipts.
    #
    # Otherwise:
    #   existing PO + no receipts
    # could return [] to the wrong supplier.

    if role == "supplier":

        supplier_id = request.state.supplier_id

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
    # 4. DEFENSIVE FILTER
    # --------------------------------------------------------

    if role == "supplier":
        return [
            receipt
            for receipt in receipts
            if receipt.get("supplier_id") == supplier_id
        ]

    return receipts


# ============================================================
# GET ALL GOODS RECEIPTS
# ============================================================

@router.get(
    "/goods-receipts",
    response_model=list[GoodsReceiptResponse],
)
def get_goods_receipts(
    request: Request,
    user=Depends(verify_token),
):
    receipts = get_all_goods_receipts()

    role = request.state.role

    # --------------------------------------------------------
    # SUPPLIER SCOPING
    # --------------------------------------------------------

    if role == "supplier":

        supplier_id = request.state.supplier_id

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