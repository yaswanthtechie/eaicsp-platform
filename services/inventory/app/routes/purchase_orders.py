from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from sqlalchemy.orm import Session

from app.core.auth import (
    require_permission,
    require_roles,
)
from app.database import get_db

from app.schemas.purchase_order import (
    PurchaseOrderRequest,
    PurchaseOrderResponse,
)

from app.services.compliance_client import (
    ComplianceServiceError,
    ComplianceServiceUnavailableError,
)

from app.services.purchase_order_service import (
    approve_purchase_order,
    create_automatic_draft_po,
    receive_purchase_order,
)


router = APIRouter(
    prefix="/api/v1/inventory/purchase-orders",
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
        require_permission("inventory:write")
    ),
):
    try:
        return create_automatic_draft_po(
            db=db,
            data=data,
        )

    except ComplianceServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    except ComplianceServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/{po_id}/approve",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_200_OK,
)
def approve_purchase_order_endpoint(
    po_id: str,
    db: Session = Depends(get_db),
    auth=Depends(
        require_roles("vp_operations")
    ),
):
    try:
        return approve_purchase_order(
            db=db,
            po_id=po_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/{po_id}/receive",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_200_OK,
)
def receive_purchase_order_endpoint(
    po_id: str,
    db: Session = Depends(get_db),
    auth=Depends(
        require_permission("inventory:write")
    ),
):
    try:
        return receive_purchase_order(
            db=db,
            po_id=po_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
