from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from app.core.auth import verify_token

from app.schemas.shipment import (
    ShipmentCreate,
    ShipmentResponse,
)

from app.services.shipment_service import (
    create_shipment,
    get_all_shipments,
    get_shipment_by_id,
    get_shipments_by_po,
)

from app.services.purchase_order_service import (
    purchase_orders,
)


router = APIRouter()


# ============================================================
# CREATE SHIPMENT NOTICE
# ============================================================

@router.post(
    "/shipments",
    response_model=ShipmentResponse,
    status_code=201,
)
def create_shipment_notice(
    shipment: ShipmentCreate,
    user=Depends(verify_token),
):
    """
    Create a Shipment Notice.

    Only authenticated suppliers can create shipment notices.

    The supplier_id is always taken from the authenticated
    Platform Service user. It is never trusted from the request.
    """

    # --------------------------------------------------------
    # 1. ONLY SUPPLIERS CAN CREATE SHIPMENTS
    # --------------------------------------------------------

    if user.get("role") != "supplier":
        raise HTTPException(
            status_code=403,
            detail="Forbidden: supplier access required",
        )

    # --------------------------------------------------------
    # 2. AUTHENTICATED SUPPLIER ID IS REQUIRED
    # --------------------------------------------------------

    supplier_id = user.get("supplier_id")

    if not supplier_id:
        raise HTTPException(
            status_code=403,
            detail="Supplier identity is missing",
        )

    # --------------------------------------------------------
    # 3. AUTHENTICATED USER IDENTITY
    # --------------------------------------------------------

    created_by = user.get("email")

    if not created_by:
        raise HTTPException(
            status_code=500,
            detail="Authenticated user identity is missing",
        )

    # --------------------------------------------------------
    # 4. CREATE SHIPMENT
    # --------------------------------------------------------

    try:
        return create_shipment(
            shipment=shipment,
            supplier_id=supplier_id,
            created_by=created_by,
        )

    except ValueError as e:
        message = str(e)

        if "Purchase Order not found" in message:
            raise HTTPException(
                status_code=404,
                detail=message,
            )

        if "does not own" in message:
            raise HTTPException(
                status_code=403,
                detail=message,
            )

        raise HTTPException(
            status_code=400,
            detail=message,
        )


# ============================================================
# GET SHIPMENT BY ID
# ============================================================

@router.get(
    "/shipments/{shipment_id}",
    response_model=ShipmentResponse,
)
def get_shipment(
    shipment_id: str,
    user=Depends(verify_token),
):
    """
    Get a Shipment Notice.

    Supplier:
        - own shipment -> 200
        - another supplier's shipment -> 403
        - missing supplier_id -> 403

    Internal authenticated users can access shipments.
    """

    shipment = get_shipment_by_id(shipment_id)

    # --------------------------------------------------------
    # UNKNOWN SHIPMENT
    # --------------------------------------------------------

    if not shipment:
        raise HTTPException(
            status_code=404,
            detail="Shipment not found",
        )

    # --------------------------------------------------------
    # SUPPLIER SCOPING
    # --------------------------------------------------------

    if user.get("role") == "supplier":

        supplier_id = user.get("supplier_id")

        if not supplier_id:
            raise HTTPException(
                status_code=403,
                detail="Supplier identity is missing",
            )

        if shipment["supplier_id"] != supplier_id:
            raise HTTPException(
                status_code=403,
                detail="Forbidden: supplier does not own this Shipment",
            )

    return shipment


# ============================================================
# GET SHIPMENTS FOR PURCHASE ORDER
# ============================================================

@router.get(
    "/purchase-orders/{po_number}/shipments",
    response_model=list[ShipmentResponse],
)
def get_po_shipments(
    po_number: str,
    user=Depends(verify_token),
):
    """
    Get all Shipment Notices for a Purchase Order.

    Supplier:
        - own PO -> shipments are returned
        - another supplier's PO -> 403
        - missing supplier_id -> 403
        - unknown PO -> 404

    Internal authenticated users can access the PO shipments.
    """

    # --------------------------------------------------------
    # 1. VERIFY THAT THE PO EXISTS
    # --------------------------------------------------------

    po = purchase_orders.get(po_number)

    if not po:
        raise HTTPException(
            status_code=404,
            detail="Purchase Order not found",
        )

    # --------------------------------------------------------
    # 2. SUPPLIER SCOPING MUST BE BASED ON THE PO
    # --------------------------------------------------------
    # Do this BEFORE checking whether shipments exist.
    #
    # This closes the previous security gap where:
    #
    #   existing PO + no shipments -> []
    #
    # could be returned without checking ownership.

    if user.get("role") == "supplier":

        supplier_id = user.get("supplier_id")

        if not supplier_id:
            raise HTTPException(
                status_code=403,
                detail="Supplier identity is missing",
            )

        if po.get("supplier_id") != supplier_id:
            raise HTTPException(
                status_code=403,
                detail="Forbidden: supplier does not own this Purchase Order",
            )

    # --------------------------------------------------------
    # 3. GET SHIPMENTS
    # --------------------------------------------------------

    po_shipments = get_shipments_by_po(po_number)

    # --------------------------------------------------------
    # 4. RETURN EMPTY LIST ONLY AFTER OWNERSHIP IS VERIFIED
    # --------------------------------------------------------

    if not po_shipments:
        return []

    # --------------------------------------------------------
    # 5. DEFENSIVE SUPPLIER FILTER
    # --------------------------------------------------------
    # Even after PO ownership is verified, filter the response
    # for supplier users so another supplier's shipment can
    # never accidentally leak through inconsistent storage.

    if user.get("role") == "supplier":

        supplier_id = user.get("supplier_id")

        return [
            shipment
            for shipment in po_shipments
            if shipment.get("supplier_id") == supplier_id
        ]

    # --------------------------------------------------------
    # 6. INTERNAL AUTHENTICATED USERS
    # --------------------------------------------------------

    return po_shipments


# ============================================================
# GET ALL SHIPMENTS
# ============================================================

@router.get(
    "/shipments",
    response_model=list[ShipmentResponse],
)
def list_shipments(
    user=Depends(verify_token),
):
    """
    Get Shipment Notices.

    Supplier:
        - only own supplier shipments
        - missing supplier_id -> 403

    Internal authenticated users:
        - all shipments
    """

    all_shipments = get_all_shipments()

    # --------------------------------------------------------
    # SUPPLIER SCOPING
    # --------------------------------------------------------

    if user.get("role") == "supplier":

        supplier_id = user.get("supplier_id")

        if not supplier_id:
            raise HTTPException(
                status_code=403,
                detail="Supplier identity is missing",
            )

        return [
            shipment
            for shipment in all_shipments
            if shipment.get("supplier_id") == supplier_id
        ]

    # --------------------------------------------------------
    # INTERNAL ROLES
    # --------------------------------------------------------

    return all_shipments