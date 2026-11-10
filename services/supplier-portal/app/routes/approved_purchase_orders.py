
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import (
    enforce_not_suspended,
    require_supplier_view_access,
    require_supplier_write_access,
    verify_token,
)
from app.database import get_db
from app.models.po_mirror import POMirror
from app.services.po_acknowledgement_service import (
    POAcknowledgementError,
    acknowledge_approved_po,
)

router = APIRouter(
    prefix="/approved-purchase-orders",
    tags=["Approved Purchase Orders"],
    dependencies=[Depends(enforce_not_suspended)],
)


def _po_response(po: POMirror) -> dict:
    return {
        "po_id": po.po_id,
        "po_number": po.po_number,
        "supplier_id": po.supplier_id,
        "warehouse_id": po.warehouse_id,
        "approval_status": po.approval_status,
        "approved_by": po.approved_by,
        "approved_at": po.approved_at,
        "total_amount": (
            float(po.total_amount)
            if isinstance(po.total_amount, Decimal)
            else po.total_amount
        ),
        "currency": po.currency,
        "expected_delivery_date": po.expected_delivery_date,
        "lines": po.lines,
        "status": po.status,
        "acknowledged_at": po.acknowledged_at,
    }


@router.get("")
def list_approved_purchase_orders(
    user=Depends(require_supplier_view_access),
    db: Session = Depends(get_db),
):
    query = db.query(POMirror)

    if user.get("role") == "supplier":
        supplier_id = user.get("supplier_id")
        if not isinstance(supplier_id, str) or not supplier_id.strip():
            raise HTTPException(
                status_code=403,
                detail="Supplier identity is missing",
            )
        query = query.filter(POMirror.supplier_id == supplier_id.strip())

    return [
        _po_response(po)
        for po in query.order_by(POMirror.approved_at.desc()).all()
    ]


@router.get("/{po_id}")
def get_approved_purchase_order(
    po_id: str,
    user=Depends(require_supplier_view_access),
    db: Session = Depends(get_db),
):
    query = db.query(POMirror).filter(POMirror.po_id == po_id)

    if user.get("role") == "supplier":
        supplier_id = user.get("supplier_id")
        if not isinstance(supplier_id, str) or not supplier_id.strip():
            raise HTTPException(
                status_code=403,
                detail="Supplier identity is missing",
            )
        query = query.filter(POMirror.supplier_id == supplier_id.strip())

    po = query.one_or_none()
    if po is None:
        # Return the same response for missing and another supplier's PO.
        raise HTTPException(status_code=404, detail="Approved PO not found")

    return _po_response(po)


@router.post("/{po_id}/acknowledge")
def acknowledge_purchase_order_endpoint(
    po_id: str,
    user=Depends(require_supplier_write_access),
    db: Session = Depends(get_db),
):
    if user.get("role") != "supplier":
        raise HTTPException(
            status_code=403,
            detail="Only the owning supplier can acknowledge a PO",
        )

    supplier_id = user.get("supplier_id")
    if not isinstance(supplier_id, str) or not supplier_id.strip():
        raise HTTPException(
            status_code=403,
            detail="Supplier identity is missing",
        )

    try:
        po = acknowledge_approved_po(
            db=db,
            po_id=po_id,
            supplier_id=supplier_id.strip(),
        )
    except POAcknowledgementError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if po is None:
        raise HTTPException(status_code=404, detail="Approved PO not found")

    return _po_response(po)
