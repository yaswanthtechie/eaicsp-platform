from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.core.auth import verify_token
from app.services.supplier_compliance_service import (
    SupplierComplianceStatus,
    supplier_compliance_service,
)


def make_po(
    po_id="PO-2026-000123",
    supplier_id="SUP-00045",
    status="approved",
):
    now = datetime.now(timezone.utc)

    return SimpleNamespace(
        po_id=po_id,
        po_number="PO-NUM-123",
        supplier_id=supplier_id,
        warehouse_id="WH-BLR-01",
        approval_status="approved",
        approved_by="inventory-manager",
        approved_at=now,
        total_amount=Decimal("1250.50"),
        currency="INR",
        expected_delivery_date=None,
        lines=[
            {
                "line_number": 1,
                "sku_id": "SKU-000123",
                "quantity": 5,
                "unit_cost": 250.10,
                "expected_cost": 250.10,
            }
        ],
        status=status,
        acknowledged_at=None,
    )


@pytest.fixture
def mock_po_api(monkeypatch):
    """
    Mock the database dependency for route tests.
    These tests do not insert records into PostgreSQL.
    """
    db = MagicMock()
    query = MagicMock()

    db.query.return_value = query
    query.filter.return_value = query
    query.order_by.return_value = query

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    # Default compliance status for route tests.
    monkeypatch.setattr(
        supplier_compliance_service,
        "get_access_status",
        lambda supplier_id: SupplierComplianceStatus.cleared,
    )

    with TestClient(app) as client:
        yield client, db, query

    app.dependency_overrides.pop(get_db, None)


def test_list_approved_purchase_orders_scopes_supplier(
    supplier_client,
    mock_po_api,
):
    client, db, query = mock_po_api
    own_po = make_po(supplier_id="SUP001")

    query.all.return_value = [own_po]

    response = supplier_client.get("/approved-purchase-orders")

    assert response.status_code == 200
    body = response.json()

    assert len(body) == 1
    assert body[0]["supplier_id"] == "SUP001"
    assert body[0]["po_id"] == own_po.po_id

    # Ensure the endpoint applies a supplier filter.
    assert query.filter.called


def test_list_approved_purchase_orders_returns_empty_list(
    supplier_client,
    mock_po_api,
):
    client, db, query = mock_po_api
    query.all.return_value = []

    response = supplier_client.get("/approved-purchase-orders")

    assert response.status_code == 200
    assert response.json() == []


def test_list_approved_purchase_orders_serializes_amount(
    supplier_client,
    mock_po_api,
):
    client, db, query = mock_po_api
    query.all.return_value = [make_po(supplier_id="SUP001")]

    response = supplier_client.get("/approved-purchase-orders")

    assert response.status_code == 200
    assert response.json()[0]["total_amount"] == 1250.50


def test_get_own_approved_purchase_order(
    supplier_client,
    mock_po_api,
):
    client, db, query = mock_po_api
    po = make_po(supplier_id="SUP001")
    query.one_or_none.return_value = po

    response = supplier_client.get(
        f"/approved-purchase-orders/{po.po_id}"
    )

    assert response.status_code == 200
    assert response.json()["po_id"] == po.po_id
    assert response.json()["supplier_id"] == "SUP001"
    assert query.filter.called


def test_get_other_suppliers_po_returns_404(
    supplier_client,
    mock_po_api,
):
    client, db, query = mock_po_api

    # Simulate the result after supplier scoping is applied.
    query.one_or_none.return_value = None

    response = supplier_client.get(
        "/approved-purchase-orders/PO-2026-999999"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Approved PO not found"


def test_get_nonexistent_po_returns_404(
    supplier_client,
    mock_po_api,
):
    client, db, query = mock_po_api
    query.one_or_none.return_value = None

    response = supplier_client.get(
        "/approved-purchase-orders/PO-2026-999998"
    )

    assert response.status_code == 404


def test_supplier_without_supplier_id_cannot_list(
    supplier_no_id_client,
    mock_po_api,
):
    response = supplier_no_id_client.get(
        "/approved-purchase-orders"
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Supplier identity is missing"


def test_supplier_without_supplier_id_cannot_get_po(
    supplier_no_id_client,
    mock_po_api,
):
    response = supplier_no_id_client.get(
        "/approved-purchase-orders/PO-2026-000123"
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Supplier identity is missing"


def test_acknowledge_own_approved_po(
    supplier_client,
    mock_po_api,
    monkeypatch,
):
    client, db, query = mock_po_api
    po = make_po(supplier_id="SUP001", status="acknowledged")
    po.acknowledged_at = datetime.now(timezone.utc)

    acknowledge = MagicMock(return_value=po)

    monkeypatch.setattr(
        "app.routes.approved_purchase_orders.acknowledge_approved_po",
        acknowledge,
    )

    response = supplier_client.post(
        f"/approved-purchase-orders/{po.po_id}/acknowledge"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "acknowledged"
    acknowledge.assert_called_once_with(
        db=db,
        po_id=po.po_id,
        supplier_id="SUP001",
    )


def test_acknowledge_po_not_found_returns_404(
    supplier_client,
    mock_po_api,
    monkeypatch,
):
    client, db, query = mock_po_api

    monkeypatch.setattr(
        "app.routes.approved_purchase_orders.acknowledge_approved_po",
        MagicMock(return_value=None),
    )

    response = supplier_client.post(
        "/approved-purchase-orders/PO-2026-999999/acknowledge"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Approved PO not found"


def test_acknowledge_invalid_status_returns_409(
    supplier_client,
    mock_po_api,
    monkeypatch,
):
    from app.services.po_acknowledgement_service import (
        POAcknowledgementError,
    )

    monkeypatch.setattr(
        "app.routes.approved_purchase_orders.acknowledge_approved_po",
        MagicMock(
            side_effect=POAcknowledgementError(
                "PO cannot be acknowledged from status 'cancelled'"
            )
        ),
    )

    response = supplier_client.post(
        "/approved-purchase-orders/PO-2026-000123/acknowledge"
    )

    assert response.status_code == 409
    assert "cannot be acknowledged" in response.json()["detail"]


def test_acknowledge_cross_supplier_po_returns_not_found(
    supplier_client,
    mock_po_api,
    monkeypatch,
):
    client, db, query = mock_po_api

    # Service returns None when the PO does not belong to the caller.
    monkeypatch.setattr(
        "app.routes.approved_purchase_orders.acknowledge_approved_po",
        MagicMock(return_value=None),
    )

    response = supplier_client.post(
        "/approved-purchase-orders/PO-2026-999999/acknowledge"
    )

    assert response.status_code == 404


def test_acknowledge_response_serializes_decimal_amount(
    supplier_client,
    mock_po_api,
    monkeypatch,
):
    po = make_po(supplier_id="SUP001", status="acknowledged")

    monkeypatch.setattr(
        "app.routes.approved_purchase_orders.acknowledge_approved_po",
        MagicMock(return_value=po),
    )

    response = supplier_client.post(
        f"/approved-purchase-orders/{po.po_id}/acknowledge"
    )

    assert response.status_code == 200
    assert response.json()["total_amount"] == 1250.50

