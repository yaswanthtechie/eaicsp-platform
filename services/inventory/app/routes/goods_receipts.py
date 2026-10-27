import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import require_permission
from app.schemas.goods_receipt import GoodsReceiptCreate, GoodsReceiptResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/goods-receipts",
    tags=["Goods Receipts"],
)


@router.post(
    "",
    response_model=GoodsReceiptResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Receive goods against an approved purchase order (Flow B)",
    description=(
        "Flow B: Warehouse manager records physical arrival of shipment. "
        "Increments on-hand stock in inventory_ledger, marks goods receipt, "
        "and emits event inventory.goods.received to Kafka for 3-way match in Supplier Portal."
    ),
    responses={
        401: {"description": "Missing or invalid token"},
        403: {"description": "Insufficient permissions"},
        501: {"description": "Not implemented yet (Round 15 stub)"},
    },
    dependencies=[
        Depends(require_permission("inventory:write")),
    ],
)
def create_goods_receipt(data: GoodsReceiptCreate):
    """
    Records physical receipt of goods (Flow B).
    Returns 501 until Flow B goods receipt recording is wired.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Flow B goods receipt recording is under construction.",
    )
