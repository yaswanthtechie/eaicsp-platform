import pytest

from app.schemas.purchase_order import PurchaseOrderStatus
from app.schemas.shipment import ShipmentCreate
from app.services.po_p2p_state_machine import (
    P2PState,
    initialize_p2p_state,
    p2p_states,
)
from app.services.purchase_order_service import (
    purchase_orders,
)
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

def test_create_shipment_successfully():
    """
    An owning supplier can create a shipment for
    an acknowledged Purchase Order.
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
                "quantity": 10,
            },
            {
                "item_code": "MOU001",
                "quantity": 10,
            },
        ],
    )

    result = create_shipment(
        shipment,
        supplier_id="SUP001",
        created_by="supplier@company.com",
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

    shipment = ShipmentCreate(
        po_number="PO1001",
        shipment_date="2026-09-09",
        expected_delivery_date="2026-09-15",
        carrier="DHL",
        tracking_number="DHL123456789",
        items=[
            {
                "item_code": "LAP001",
                "quantity": 10,
            },
        ],
    )

    create_shipment(
        shipment,
        supplier_id="SUP001",
        created_by="supplier@company.com",
    )

    assert (
        p2p_states["PO1001"]
        == P2PState.shipped
    )

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

def test_shipment_is_stored():
    """
    Successfully created shipment must be persisted
    in shipment storage.
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
        ],
    )

    result = create_shipment(
        shipment,
        supplier_id="SUP001",
        created_by="supplier@company.com",
    )

    shipment_id = result["shipment_id"]

    assert shipment_id in shipments
    assert (
        get_shipment_by_id(shipment_id)
        == result
    )

def test_get_shipments_by_po():
    """
    Shipments can be retrieved using the Purchase Order number.
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
        ],
    )

    result = create_shipment(
        shipment,
        supplier_id="SUP001",
        created_by="supplier@company.com",
    )

    results = get_shipments_by_po(
        "PO1001"
    )

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

