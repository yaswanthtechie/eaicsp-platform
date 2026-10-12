import logging

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
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
    ComplianceBlockedError,
    ComplianceServiceError,
    ComplianceServiceUnavailableError,
)

from app.services.purchase_order_service import (
    approve_purchase_order,
    create_automatic_draft_po,
    get_purchase_order,
    list_purchase_orders,
    receive_purchase_order,
)


logger = logging.getLogger(__name__)

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

    except ComplianceBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

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

    except Exception as exc:
        logger.exception("Unexpected error creating draft purchase order")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create draft purchase order",
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


@router.get(
    "",
    response_model=list[PurchaseOrderResponse],
    status_code=status.HTTP_200_OK,
)
def list_purchase_orders_endpoint(
    po_id: str | None = Query(None, description="Filter by purchase order ID (e.g. PO-7F78FAE0)"),
    supplier_id: str | None = Query(None, description="Filter by supplier ID (e.g. SUP001)"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status (e.g. draft, on_hold, received)"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    auth=Depends(
        require_permission("inventory:read")
    ),
):
    return list_purchase_orders(
        db=db,
        po_id=po_id,
        supplier_id=supplier_id,
        status=status_filter,
        limit=limit,
    )


@router.get(
    "/{po_id}",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_200_OK,
)
def get_purchase_order_endpoint(
    po_id: str,
    db: Session = Depends(get_db),
    auth=Depends(
        require_permission("inventory:read")
    ),
):
    try:
        return get_purchase_order(
            db=db,
            po_id=po_id,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.api_route("/{rest_of_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def purchase_orders_catch_all(rest_of_path: str):
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

