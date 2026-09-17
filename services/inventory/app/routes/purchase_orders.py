from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from app.core.auth import require_roles
from sqlalchemy.orm import Session

from app.database import get_db

from app.schemas.purchase_order import (
    PurchaseOrderRequest,
    PurchaseOrderResponse,
)

from app.services.purchase_order_service import (
    create_automatic_draft_po,
)


router = APIRouter(
    prefix="/api/v1/purchase-orders",
    tags=["Purchase Orders"],
)


@router.post(
    "/draft",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_purchase_order(
    data: PurchaseOrderRequest,
    db: Session = Depends(get_db),
    auth=Depends(
            require_roles(
                "warehouse_manager",
                "procurement_manager",
            )
        ),
):

    try:

        return create_automatic_draft_po(
            db=db,
            data=data,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )