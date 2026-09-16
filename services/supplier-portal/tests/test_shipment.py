import pytest

from app.schemas.purchase_order import PurchaseOrderStatus
from app.schemas.shipment import ShipmentCreate
from app.services.po_p2p_state_machine import (
    P2PState,
    initialize_p2p_state,
    p2p_states,
)
from app.services.purchase_order_service import purchase_orders
from app.services.shipment_service import (
    shipments,
    create_shipment,
    get_shipment_by_id,
    get_shipments_by_po,
    get_all_shipments,
)


@pytest.fixture(autouse=True)
def clear_storage():
    """
    Clear Shipment, Purchase Order and P2P state
    before and after every test.
    """

    shipments.clear()
    purchase_orders.clear()
    p2p_states.clear()

    yield

    shipments.clear()
    purchase_orders.clear()
    p2p_states.clear()


def create_acknowledged_po(
    po_number="PO1001",
    supplier_id="SUP001",
):
    purchase_orders[po_number] = {
        "po_number": po_number,
        "supplier_id": supplier_id,
        "items": [
            {
                "item_code": "LAP001",
                "description": "Laptop",
                "quantity": 10,
                "unit_price": 50000,
            },
            {
                "item_code": "MOU001",
                "description": "Wireless Mouse",
                "quantity": 10,
                "unit_price": 1500,
            },
        ],
        "total_amount": 515000,
        "status": PurchaseOrderStatus.acknowledged,
        "created_at": None,
        "expected_delivery": None,
        "actual_delivery_date": None,
        "history": [],
    }

    initialize_p2p_state(
        po_number,
        P2PState.acknowledged,
    )


def create_shipment_for_supplier(
    po_number="PO1001",
    supplier_id="SUP001",
    quantity=5,
    created_by="supplier@company.com",
):
    shipment = ShipmentCreate(
        po_number=po_number,
        shipment_date="2026-09-09",
        expected_delivery_date="2026-09-15",
        carrier="DHL",
        tracking_number="DHL123456789",
        items=[
            {
                "item_code": "LAP001",
                "quantity": quantity,
            },
        ],
    )

    return create_shipment(
        shipment,
        supplier_id=supplier_id,
        created_by=created_by,
    )


# ============================================================
# CREATE SHIPMENT
# ============================================================


def test_create_shipment_successfully():
    """
    An owning supplier can create a shipment for
    an acknowledged Purchase Order.
    """

    create_acknowledged_po()

    result = create_shipment_for_supplier(
        quantity=10,
    )

    assert result["po_number"] == "PO1001"
    assert result["supplier_id"] == "SUP001"
    assert result["carrier"] == "DHL"
    assert result["tracking_number"] == "DHL123456789"
    assert result["status"] == "created"


def test_shipment_moves_p2p_state_to_shipped():
    """
    Creating a valid shipment must move the shared
    P2P workflow from acknowledged to shipped.
    """

    create_acknowledged_po()

    create_shipment_for_supplier()

    assert p2p_states["PO1001"] == P2PState.shipped


def test_cross_supplier_shipment_is_rejected():
    """
    Supplier A must not be able to create a shipment
    for Supplier B's Purchase Order.
    """

    create_acknowledged_po(
        po_number="PO2001",
        supplier_id="SUP002",
    )

    shipment = ShipmentCreate(
        po_number="PO2001",
        shipment_date="2026-09-09",
        expected_delivery_date="2026-09-15",
        carrier="DHL",
        tracking_number="DHL123456789",
        items=[
            {
                "item_code": "LAP001",
                "quantity": 5,
            },
        ],
    )

    with pytest.raises(
        ValueError,
        match="does not own",
    ):
        create_shipment(
            shipment,
            supplier_id="SUP001",
            created_by="supplier@company.com",
        )


def test_shipment_for_nonexistent_po_is_rejected():
    """
    Shipment cannot be created for a PO that does not exist.
    """

    shipment = ShipmentCreate(
        po_number="PO9999",
        shipment_date="2026-09-09",
        expected_delivery_date="2026-09-15",
        carrier="DHL",
        tracking_number="DHL123456789",
        items=[
            {
                "item_code": "LAP001",
                "quantity": 5,
            },
        ],
    )

    with pytest.raises(
        ValueError,
        match="Purchase Order not found",
    ):
        create_shipment(
            shipment,
            supplier_id="SUP001",
            created_by="supplier@company.com",
        )


def test_shipment_before_acknowledgment_is_rejected():
    """
    Shipment cannot be created before PO acknowledgment.
    """

    purchase_orders["PO1001"] = {
        "po_number": "PO1001",
        "supplier_id": "SUP001",
        "items": [
            {
                "item_code": "LAP001",
                "description": "Laptop",
                "quantity": 10,
                "unit_price": 50000,
            },
        ],
        "total_amount": 500000,
        "status": PurchaseOrderStatus.sent,
        "created_at": None,
        "expected_delivery": None,
        "actual_delivery_date": None,
        "history": [],
    }

    shipment = ShipmentCreate(
        po_number="PO1001",
        shipment_date="2026-09-09",
        expected_delivery_date="2026-09-15",
        carrier="DHL",
        tracking_number="DHL123456789",
        items=[
            {
                "item_code": "LAP001",
                "quantity": 5,
            },
        ],
    )

    with pytest.raises(
        ValueError,
        match="acknowledged",
    ):
        create_shipment(
            shipment,
            supplier_id="SUP001",
            created_by="supplier@company.com",
        )


def test_shipment_requires_acknowledged_p2p_state():
    """
    Even if the PO status is acknowledged, Shipment must
    not proceed if the shared P2P state is not acknowledged.
    """

    create_acknowledged_po()

    p2p_states["PO1001"] = P2PState.received

    shipment = ShipmentCreate(
        po_number="PO1001",
        shipment_date="2026-09-09",
        expected_delivery_date="2026-09-15",
        carrier="DHL",
        tracking_number="DHL123456789",
        items=[
            {
                "item_code": "LAP001",
                "quantity": 5,
            },
        ],
    )

    with pytest.raises(
        ValueError,
        match="acknowledged P2P state",
    ):
        create_shipment(
            shipment,
            supplier_id="SUP001",
            created_by="supplier@company.com",
        )


def test_shipment_with_unknown_item_is_rejected():
    """
    Shipment item must exist in the Purchase Order.
    """

    create_acknowledged_po()

    shipment = ShipmentCreate(
        po_number="PO1001",
        shipment_date="2026-09-09",
        expected_delivery_date="2026-09-15",
        carrier="DHL",
        tracking_number="DHL123456789",
        items=[
            {
                "item_code": "UNKNOWN",
                "quantity": 5,
            },
        ],
    )

    with pytest.raises(
        ValueError,
        match="does not exist",
    ):
        create_shipment(
            shipment,
            supplier_id="SUP001",
            created_by="supplier@company.com",
        )


def test_shipment_quantity_cannot_exceed_po_quantity():
    """
    Shipment quantity cannot exceed the quantity ordered
    in the Purchase Order.
    """

    create_acknowledged_po()

    shipment = ShipmentCreate(
        po_number="PO1001",
        shipment_date="2026-09-09",
        expected_delivery_date="2026-09-15",
        carrier="DHL",
        tracking_number="DHL123456789",
        items=[
            {
                "item_code": "LAP001",
                "quantity": 11,
            },
        ],
    )

    with pytest.raises(
        ValueError,
        match="exceeds",
    ):
        create_shipment(
            shipment,
            supplier_id="SUP001",
            created_by="supplier@company.com",
        )


def test_duplicate_shipment_item_is_rejected():
    """
    The same item code cannot appear twice in one shipment.
    """

    create_acknowledged_po()

    shipment = ShipmentCreate(
        po_number="PO1001",
        shipment_date="2026-09-09",
        expected_delivery_date="2026-09-15",
        carrier="DHL",
        tracking_number="DHL123456789",
        items=[
            {
                "item_code": "LAP001",
                "quantity": 5,
            },
            {
                "item_code": "LAP001",
                "quantity": 5,
            },
        ],
    )

    with pytest.raises(
        ValueError,
        match="Duplicate shipment item",
    ):
        create_shipment(
            shipment,
            supplier_id="SUP001",
            created_by="supplier@company.com",
        )


# ============================================================
# STORAGE
# ============================================================


def test_shipment_is_stored():
    """
    Successfully created shipment must be persisted
    in shipment storage.
    """

    create_acknowledged_po()

    result = create_shipment_for_supplier()

    shipment_id = result["shipment_id"]

    assert shipment_id in shipments
    assert get_shipment_by_id(shipment_id) == result


def test_get_shipments_by_po():
    """
    Shipments can be retrieved using the Purchase Order number.
    """

    create_acknowledged_po()

    result = create_shipment_for_supplier()

    results = get_shipments_by_po("PO1001")

    assert len(results) == 1
    assert results[0]["shipment_id"] == result["shipment_id"]


def test_get_all_shipments():
    """
    All stored shipments can be retrieved.
    """

    create_acknowledged_po(
        po_number="PO1001",
        supplier_id="SUP001",
    )

    create_acknowledged_po(
        po_number="PO1002",
        supplier_id="SUP002",
    )

    shipment1 = ShipmentCreate(
        po_number="PO1001",
        shipment_date="2026-09-09",
        expected_delivery_date="2026-09-15",
        carrier="DHL",
        tracking_number="DHL111",
        items=[
            {
                "item_code": "LAP001",
                "quantity": 5,
            },
        ],
    )

    shipment2 = ShipmentCreate(
        po_number="PO1002",
        shipment_date="2026-09-09",
        expected_delivery_date="2026-09-15",
        carrier="FedEx",
        tracking_number="FDX222",
        items=[
            {
                "item_code": "LAP001",
                "quantity": 5,
            },
        ],
    )

    create_shipment(
        shipment1,
        supplier_id="SUP001",
        created_by="supplier1@company.com",
    )

    create_shipment(
        shipment2,
        supplier_id="SUP002",
        created_by="supplier2@company.com",
    )

    results = get_all_shipments()

    assert len(results) == 2


# ============================================================
# CREATED_AT / TIMEZONE
# ============================================================


def test_shipment_created_at_is_timezone_aware():
    """
    Shipment timestamps must use timezone-aware UTC datetimes.
    This prevents the deprecated datetime.utcnow() usage.
    """

    create_acknowledged_po()

    result = create_shipment_for_supplier()

    created_at = result["created_at"]

    assert created_at.tzinfo is not None
    assert created_at.utcoffset() is not None


# ============================================================
# API SECURITY / SUPPLIER SCOPING
# ============================================================


def test_supplier_can_view_own_shipment(
    supplier_client,
):
    """
    A supplier can retrieve its own shipment.
    """

    create_acknowledged_po(
        po_number="PO1001",
        supplier_id="SUP001",
    )

    result = create_shipment_for_supplier(
        po_number="PO1001",
        supplier_id="SUP001",
    )

    response = supplier_client.get(
        f"/api/v1/shipments/{result['shipment_id']}"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["shipment_id"] == result["shipment_id"]
    assert body["supplier_id"] == "SUP001"


def test_supplier_cannot_view_another_suppliers_shipment(
    supplier_client,
):
    """
    A supplier must not access another supplier's shipment.
    """

    create_acknowledged_po(
        po_number="PO2001",
        supplier_id="SUP002",
    )

    # Shipment creation changes the P2P state only for PO2001.
    result = create_shipment_for_supplier(
        po_number="PO2001",
        supplier_id="SUP002",
        created_by="supplierb@example.com",
    )

    response = supplier_client.get(
        f"/api/v1/shipments/{result['shipment_id']}"
    )

    assert response.status_code == 403

    assert (
        "forbidden"
        in response.json()["detail"].lower()
    )


def test_supplier_cannot_determine_unknown_shipment_existence(
    supplier_client,
):
    """
    Unknown shipment IDs must return the same forbidden response
    class used for inaccessible shipments.

    This prevents a supplier from determining whether another
    supplier's shipment exists.
    """

    response = supplier_client.get(
        "/api/v1/shipments/SHIP-DOES-NOT-EXIST"
    )

    assert response.status_code == 403

    assert (
        "shipment is not accessible"
        in response.json()["detail"].lower()
    )


def test_supplier_without_supplier_id_cannot_view_shipment(
    supplier_no_id_client,
):
    """
    A supplier without supplier_id must not access shipment data.
    """

    response = supplier_no_id_client.get(
        "/api/v1/shipments/SHIP-DOES-NOT-EXIST"
    )

    assert response.status_code == 403

    assert (
        "supplier identity is missing"
        in response.json()["detail"].lower()
    )


def test_internal_user_gets_404_for_unknown_shipment(
    procurement_client,
):
    """
    Internal authenticated users may receive 404 for a genuinely
    unknown shipment because they are not subject to supplier
    existence protection.
    """

    response = procurement_client.get(
        "/api/v1/shipments/SHIP-DOES-NOT-EXIST"
    )

    assert response.status_code == 404

    assert (
        "shipment not found"
        in response.json()["detail"].lower()
    )


def test_internal_user_can_view_existing_supplier_shipment(
    procurement_client,
):
    """
    Internal authenticated users can retrieve an existing shipment
    regardless of supplier ownership.
    """

    create_acknowledged_po(
        po_number="PO2001",
        supplier_id="SUP002",
    )

    result = create_shipment_for_supplier(
        po_number="PO2001",
        supplier_id="SUP002",
        created_by="supplierb@example.com",
    )

    response = procurement_client.get(
        f"/api/v1/shipments/{result['shipment_id']}"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["shipment_id"] == result["shipment_id"]
    assert body["supplier_id"] == "SUP002"


# ============================================================
# API SUPPLIER LIST SCOPING
# ============================================================


def test_supplier_list_shipments_returns_only_own_shipments(
    supplier_client,
):
    """
    Supplier list endpoint must return only shipments belonging
    to the authenticated supplier.
    """

    create_acknowledged_po(
        po_number="PO1001",
        supplier_id="SUP001",
    )

    create_acknowledged_po(
        po_number="PO2001",
        supplier_id="SUP002",
    )

    create_shipment_for_supplier(
        po_number="PO1001",
        supplier_id="SUP001",
        created_by="supplier@company.com",
    )

    create_shipment_for_supplier(
        po_number="PO2001",
        supplier_id="SUP002",
        created_by="supplierb@example.com",
    )

    response = supplier_client.get(
        "/api/v1/shipments"
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1
    assert body[0]["supplier_id"] == "SUP001"


def test_internal_user_can_list_all_shipments(
    procurement_client,
):
    """
    Internal authenticated users can retrieve shipments across
    suppliers.
    """

    create_acknowledged_po(
        po_number="PO1001",
        supplier_id="SUP001",
    )

    create_acknowledged_po(
        po_number="PO2001",
        supplier_id="SUP002",
    )

    create_shipment_for_supplier(
        po_number="PO1001",
        supplier_id="SUP001",
        created_by="supplier@company.com",
    )

    create_shipment_for_supplier(
        po_number="PO2001",
        supplier_id="SUP002",
        created_by="supplierb@example.com",
    )

    response = procurement_client.get(
        "/api/v1/shipments"
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 2

    supplier_ids = {
        shipment["supplier_id"]
        for shipment in body
    }

    assert supplier_ids == {
        "SUP001",
        "SUP002",
    }

