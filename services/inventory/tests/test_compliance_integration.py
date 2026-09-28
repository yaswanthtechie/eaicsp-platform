import logging

import httpx
import pytest

from app.models.inventory import Inventory
from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier
from app.services import compliance_client
from app.services.compliance_client import (
    ComplianceServiceError,
    ComplianceServiceUnavailableError,
    check_supplier_compliance,
)
from tests.conftest import seed_sales_history


SKU = "SKU-COMP"
WAREHOUSE = "WH-COMP"


# ============================================================
# HELPERS
# ============================================================

def use_compliance_response(monkeypatch, handler):
    """
    Route the client's real httpx calls to `handler`
    instead of the network.
    """

    real_client = httpx.Client

    def fake_client(**kwargs):
        return real_client(
            transport=httpx.MockTransport(handler),
            **kwargs,
        )

    monkeypatch.setattr(
        compliance_client.httpx,
        "Client",
        fake_client,
    )


def compliance_returns(monkeypatch, decision):
    """Patch the service-layer call to return a fixed decision."""

    def fake(supplier_id, supplier_name, country):
        return {
            "decision": decision,
            "cleared": decision == "CLEAR",
            "reason": f"Test {decision}",
        }

    monkeypatch.setattr(
        "app.services.purchase_order_service.check_supplier_compliance",
        fake,
    )


def compliance_raises(monkeypatch, error):
    def fake(supplier_id, supplier_name, country):
        raise error

    monkeypatch.setattr(
        "app.services.purchase_order_service.check_supplier_compliance",
        fake,
    )


def seed_supplier_and_demand(db_session):
    db_session.add(
        Supplier(
            supplier_id="SUP-COMP",
            sku_id=SKU,
            supplier_name="Compliance Supplier",
            unit_cost=10.0,
            lead_time_days=5,
        )
    )
    db_session.commit()

    # 10/day demand, 5-day lead time, safety stock 10 -> ROP 60
    seed_sales_history(SKU, WAREHOUSE, daily_quantity=10)


def inventory_body(quantity):
    return {
        "sku_id": SKU,
        "product_name": "Compliance Widget",
        "warehouse_id": WAREHOUSE,
        "category": "Widgets",
        "quantity_on_hand": quantity,
        "lead_time_days": 5,
        "safety_stock": 10,
        "warehouse_type": "local",
        "unit_cost": 10.0,
    }


def po_count(db_session):
    return (
        db_session.query(PurchaseOrder)
        .filter(PurchaseOrder.sku_id == SKU)
        .count()
    )


def stock_in_db(db_session):
    db_session.expire_all()
    row = (
        db_session.query(Inventory)
        .filter(
            Inventory.sku_id == SKU,
            Inventory.warehouse_id == WAREHOUSE,
        )
        .first()
    )
    return None if row is None else row.quantity_on_hand


# ============================================================
# CLIENT: response handling
# ============================================================

@pytest.mark.parametrize("decision", ["CLEAR", "BLOCK", "REVIEW"])
def test_client_returns_valid_decisions(monkeypatch, decision):
    use_compliance_response(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            json={"decision": decision, "cleared": decision == "CLEAR"},
        ),
    )

    result = check_supplier_compliance("SUP-1", "Acme", "India")

    assert result["decision"] == decision


def test_client_sends_supplier_details_to_internal_check(monkeypatch):
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["body"] = request.read()
        seen["caller"] = request.headers.get("X-Caller-Service")
        return httpx.Response(
            200,
            json={"decision": "CLEAR", "cleared": True},
        )

    use_compliance_response(monkeypatch, handler)

    check_supplier_compliance("SUP-1", "Acme", "India")

    assert seen["path"] == "/api/v1/compliance/internal-check"
    assert b'"supplier_id":"SUP-1"' in seen["body"].replace(b" ", b"")
    assert seen["caller"] == "inventory-service"


@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectError("refused"),
        httpx.ConnectTimeout("slow"),
        httpx.ReadTimeout("slow"),
    ],
)
def test_client_network_failures_are_unavailable(monkeypatch, error):
    def handler(request):
        raise error

    use_compliance_response(monkeypatch, handler)

    with pytest.raises(ComplianceServiceUnavailableError):
        check_supplier_compliance("SUP-1", "Acme", "India")


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, json={"detail": "boom"}),
        httpx.Response(404, json={"detail": "Not Found"}),
        httpx.Response(200, content=b"not json"),
        httpx.Response(200, json=["CLEAR"]),
        httpx.Response(200, json={"decision": "MAYBE", "cleared": True}),
        httpx.Response(200, json={"decision": "CLEAR", "cleared": "yes"}),
        # contradictory: CLEAR but not cleared, BLOCK but cleared
        httpx.Response(200, json={"decision": "CLEAR", "cleared": False}),
        httpx.Response(200, json={"decision": "BLOCK", "cleared": True}),
    ],
)
def test_client_unusable_responses_are_errors(monkeypatch, response):
    use_compliance_response(monkeypatch, lambda request: response)

    with pytest.raises(ComplianceServiceError):
        check_supplier_compliance("SUP-1", "Acme", "India")


# ============================================================
# AUTOMATIC PO PATH: stock movement must never fail
# ============================================================

def test_decrement_succeeds_and_warns_when_compliance_down(
    client,
    db_session,
    monkeypatch,
    caplog,
):
    seed_supplier_and_demand(db_session)
    client.post("/api/v1/inventory", json=inventory_body(500))

    compliance_raises(
        monkeypatch,
        ComplianceServiceUnavailableError("Compliance Service is unavailable."),
    )

    with caplog.at_level(logging.WARNING):
        response = client.post(
            "/api/v1/inventory/decrement",
            params={"sku_id": SKU, "warehouse_id": WAREHOUSE, "quantity": 460},
        )

    # The sale happened, so the caller must be told it succeeded;
    # a 500 here makes clients retry and deduct the stock twice.
    assert response.status_code == 200, response.text
    assert response.json()["quantity_on_hand"] == 40
    assert stock_in_db(db_session) == 40
    assert po_count(db_session) == 0
    assert any(
        "Compliance check failed" in message
        for message in caplog.messages
    )


def test_create_below_rop_succeeds_when_compliance_down(
    client,
    db_session,
    monkeypatch,
):
    seed_supplier_and_demand(db_session)

    compliance_raises(
        monkeypatch,
        ComplianceServiceUnavailableError("Compliance Service is unavailable."),
    )

    response = client.post("/api/v1/inventory", json=inventory_body(5))

    assert response.status_code == 201, response.text
    assert stock_in_db(db_session) == 5
    assert po_count(db_session) == 0


@pytest.mark.parametrize("decision", ["BLOCK", "REVIEW"])
def test_blocked_supplier_skips_po_with_visible_warning(
    client,
    db_session,
    monkeypatch,
    caplog,
    decision,
):
    seed_supplier_and_demand(db_session)
    client.post("/api/v1/inventory", json=inventory_body(500))

    compliance_returns(monkeypatch, decision)

    with caplog.at_level(logging.WARNING):
        response = client.post(
            "/api/v1/inventory/decrement",
            params={"sku_id": SKU, "warehouse_id": WAREHOUSE, "quantity": 460},
        )

    assert response.status_code == 200
    assert po_count(db_session) == 0

    warnings = [
        message
        for message in caplog.messages
        if "Automatic PO not created" in message
    ]
    assert warnings, "a skipped reorder must leave a trace"
    assert decision in warnings[0]
    assert "SUP-COMP" in warnings[0]


def test_po_is_created_on_next_movement_once_compliance_recovers(
    client,
    db_session,
    monkeypatch,
):
    seed_supplier_and_demand(db_session)
    client.post("/api/v1/inventory", json=inventory_body(500))

    compliance_raises(
        monkeypatch,
        ComplianceServiceUnavailableError("down"),
    )
    client.post(
        "/api/v1/inventory/decrement",
        params={"sku_id": SKU, "warehouse_id": WAREHOUSE, "quantity": 460},
    )
    assert po_count(db_session) == 0

    compliance_returns(monkeypatch, "CLEAR")
    client.post(
        "/api/v1/inventory/decrement",
        params={"sku_id": SKU, "warehouse_id": WAREHOUSE, "quantity": 1},
    )
    assert po_count(db_session) == 1


# ============================================================
# MANUAL DRAFT ENDPOINT: caller gets the real reason
# ============================================================

@pytest.mark.parametrize(
    "setup, expected_status",
    [
        (lambda mp: compliance_returns(mp, "BLOCK"), 409),
        (lambda mp: compliance_returns(mp, "REVIEW"), 409),
        (
            lambda mp: compliance_raises(
                mp, ComplianceServiceUnavailableError("down")
            ),
            503,
        ),
        (
            lambda mp: compliance_raises(
                mp, ComplianceServiceError("bad response")
            ),
            502,
        ),
    ],
)
def test_manual_draft_reports_compliance_outcome(
    client,
    db_session,
    monkeypatch,
    setup,
    expected_status,
):
    seed_supplier_and_demand(db_session)
    db_session.add(
        Inventory(
            sku_id=SKU,
            product_name="Compliance Widget",
            warehouse_id=WAREHOUSE,
            category="Widgets",
            quantity_on_hand=5,
            lead_time_days=5,
            safety_stock=10,
            warehouse_type="local",
        )
    )
    db_session.commit()

    setup(monkeypatch)

    response = client.post(
        "/api/v1/inventory/purchase-orders/draft",
        json={"sku_id": SKU, "warehouse_id": WAREHOUSE},
    )

    assert response.status_code == expected_status, response.text
    assert po_count(db_session) == 0
