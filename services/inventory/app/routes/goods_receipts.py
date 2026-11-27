import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import require_permission, require_roles
from app.database import get_db
from app.schemas.goods_receipt import GoodsReceiptCreate, GoodsReceiptResponse
from app.services.goods_receipt_service import (
    invalidate_receipt_cache,
    record_goods_receipt,
)
from app.services.idempotency_service import execute_idempotent

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
        409: {"description": "Idempotency-Key conflict with different request body"},
    },
    dependencies=[
        Depends(require_permission("inventory:write")),
    ],
)
def create_goods_receipt(
    data: GoodsReceiptCreate,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        description="Optional idempotency key for safe request retries.",
    ),
    db: Session = Depends(get_db),
    auth: dict = Depends(require_roles("warehouse_manager")),
):
    """
    Records physical receipt of goods (Flow B).
    Increments on-hand stock, updates purchase order status, and publishes inventory.goods.received outbox event.
    """
    user_id = auth.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has no user_id",
        )
    received_by = str(user_id)

    try:
        return execute_idempotent(
            db=db,
            idempotency_key=idempotency_key,
            scope="POST:/api/v1/inventory/goods-receipts",
            request_payload=data,
            success_status_code=status.HTTP_201_CREATED,
            action=lambda: record_goods_receipt(
                db=db,
                data=data,
                received_by=received_by,
            ),
            serialize=lambda receipt: GoodsReceiptResponse.model_validate(receipt),
            after_commit=lambda receipt: invalidate_receipt_cache(db, receipt),
        )

    except HTTPException:
        raise

    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
