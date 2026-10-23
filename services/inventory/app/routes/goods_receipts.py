import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import require_permission, require_roles
from app.database import get_db
from app.schemas.goods_receipt import GoodsReceiptCreate, GoodsReceiptResponse
from app.services.goods_receipt_service import record_goods_receipt

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
    },
    dependencies=[
        Depends(require_permission("inventory:write")),
    ],
)
def create_goods_receipt(
    data: GoodsReceiptCreate,
    db: Session = Depends(get_db),
    auth: dict = Depends(require_roles("warehouse_manager")),
):
    """
    Records physical receipt of goods (Flow B).
    Increments on-hand stock, updates purchase order status, and publishes inventory.goods.received outbox event.
    """
    received_by = str(
        auth.get("username")
        or auth.get("email")
        or auth.get("user_id")
        or "warehouse_manager"
    )

    try:
        receipt = record_goods_receipt(
            db=db,
            data=data,
            received_by=received_by,
        )
        db.commit()
        db.refresh(receipt)
        return receipt

    except LookupError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except Exception:
        db.rollback()
        raise
