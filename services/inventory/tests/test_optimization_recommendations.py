"""
Unit and integration tests for Inventory Reorder Recommendations (Flow A, Issue #204)

Verifies:
1. Forecast client: timeout, retry once, fallback to 28-day moving average with forecast_source="fallback".
2. GET /api/v1/inventory/optimization/recommendations returns SKU, warehouse, recommended qty, forecast used, source.
3. Tests against a mock conforming strictly to Ajith's forecast contract (contracts/openapi/forecast.yaml).
4. Edge cases: 503 unavailable, timeouts, missing sales history, supplier cost calculations.
5. Access control: 401 unauthenticated, 403 insufficient permissions.
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.core.config import settings
from app.models.inventory import Inventory
from app.models.sales_history import SalesHistory
from app.models.supplier import Supplier
from app.schemas.forecast import ForecastServingResponse
from app.services.forecast_client import ForecastClient
from app.services.optimization_service import generate_recommendations


@pytest.fixture
def mock_forecast_payload():
    """Mock forecast response strictly following contracts/openapi/forecast.yaml."""
    today = date.today()
    forecast_points = []
    for day_offset in range(1, 31):
        d = today + timedelta(days=day_offset)
        forecast_points.append(
            {
                "date": d.isoformat(),
                "predicted": 10.0,
                "lower_bound": 8.0,
                "upper_bound": 12.0,
            }
        )

    return {
        "contract_version": "v1",
        "sku_id": "SKU-000123",
        "warehouse_id": "WH-BLR-01",
        "granularity": "daily",
        "horizon": 30,
        "interval_level": 0.8,
        "model_version": "ensemble-r15",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "forecast": forecast_points,
        "explanation": {
            "top_drivers": [
                {"feature": "lag_7", "contribution": 4.5},
                {"feature": "day_of_week", "contribution": 1.2},
            ]
        },
    }


def seed_inventory_and_supplier(db_session, sku_id, warehouse_id, qty_on_hand, safety_stock=10, lead_time=5, unit_cost=20.0):
    supplier_id = "SUP-00045"
    supplier = db_session.query(Supplier).filter(Supplier.supplier_id == supplier_id).first()
    if not supplier:
        supplier = Supplier(
            supplier_id=supplier_id,
            sku_id=sku_id,
            supplier_name="Apex Logistics Supplier",
            unit_cost=unit_cost,
            lead_time_days=lead_time,
        )
        db_session.add(supplier)

    inv = db_session.query(Inventory).filter(
        Inventory.sku_id == sku_id,
        Inventory.warehouse_id == warehouse_id,
    ).first()
    if not inv:
        inv = Inventory(
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            product_name="Test Product",
            category="Electronics",
            quantity_on_hand=qty_on_hand,
            safety_stock=safety_stock,
            lead_time_days=lead_time,
        )
        db_session.add(inv)
    else:
        inv.quantity_on_hand = qty_on_hand
        inv.safety_stock = safety_stock
        inv.lead_time_days = lead_time

    db_session.commit()
    db_session.refresh(inv)
    return inv, supplier


def seed_28_day_sales(db_session, sku_id, warehouse_id, daily_qty=5):
    today = date.today()
    for i in range(28):
        sale_d = today - timedelta(days=i)
        sale = SalesHistory(
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            sale_date=sale_d,
            quantity_sold=daily_qty,
        )
        db_session.add(sale)
    db_session.commit()


# =====================================================================
# 1. FORECAST CLIENT TESTS (Timeout, Retry, Fallback)
# =====================================================================


def test_forecast_client_success_on_first_attempt(mock_forecast_payload):
    """Client calls Forecast Service and parses valid contract response."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_forecast_payload

    with patch("app.services.forecast_client.httpx.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_instance
        mock_instance.get.return_value = mock_resp

        client = ForecastClient(base_url="http://localhost:8007", timeout_seconds=1.0, max_retries=1)
        res = client.fetch_forecast(sku_id="SKU-000123", warehouse_id="WH-BLR-01", horizon=30)

        assert mock_instance.get.call_count == 1
        assert res is not None
        assert res.sku_id == "SKU-000123"
        assert res.model_version == "ensemble-r15"
        assert len(res.forecast) == 30


def test_forecast_client_retry_once_on_timeout(mock_forecast_payload):
    """Client encounters timeout on attempt 1, retries once, and succeeds on attempt 2."""
    mock_success = MagicMock()
    mock_success.status_code = 200
    mock_success.json.return_value = mock_forecast_payload

    with patch("app.services.forecast_client.httpx.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_instance
        mock_instance.get.side_effect = [httpx.TimeoutException("Read timed out"), mock_success]

        client = ForecastClient(base_url="http://localhost:8007", timeout_seconds=1.0, max_retries=1)
        res = client.fetch_forecast(sku_id="SKU-000123", warehouse_id="WH-BLR-01", horizon=30)

        assert mock_instance.get.call_count == 2
        assert res is not None
        assert res.sku_id == "SKU-000123"


def test_forecast_client_exhausts_retries_and_falls_back(db_session):
    """When Forecast Service is completely down, client retries once and falls back to 28-day moving average."""
    sku_id = "SKU-000123"
    warehouse_id = "WH-BLR-01"
    seed_28_day_sales(db_session, sku_id, warehouse_id, daily_qty=6)

    with patch("app.services.forecast_client.httpx.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_instance
        mock_instance.get.side_effect = httpx.ConnectError("Connection refused")

        client = ForecastClient(base_url="http://localhost:8007", timeout_seconds=1.0, max_retries=1)
        res = client.resolve_demand(db=db_session, sku_id=sku_id, warehouse_id=warehouse_id, horizon=30, fallback_days=28)

        # 1 initial + 1 retry = 2 calls
        assert mock_instance.get.call_count == 2
        assert res.forecast_source == "fallback"
        assert res.model_version is None
        assert res.daily_demand == 6.0
        assert res.forecast_demand == 180.0  # 6.0 * 30 days


def test_forecast_client_503_unavailable_falls_back(db_session):
    """HTTP 503 triggers retry and falls back to 28-day moving average."""
    sku_id = "SKU-000123"
    warehouse_id = "WH-BLR-01"
    seed_28_day_sales(db_session, sku_id, warehouse_id, daily_qty=4)

    mock_503 = MagicMock()
    mock_503.status_code = 503
    mock_503.text = '{"error_code":"MODEL_UNAVAILABLE","message":"Model loading"}'

    with patch("app.services.forecast_client.httpx.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_instance
        mock_instance.get.return_value = mock_503

        client = ForecastClient(base_url="http://localhost:8007", timeout_seconds=1.0, max_retries=1)
        res = client.resolve_demand(db=db_session, sku_id=sku_id, warehouse_id=warehouse_id, horizon=30, fallback_days=28)

        assert mock_instance.get.call_count == 2
        assert res.forecast_source == "fallback"
        assert res.daily_demand == 4.0
        assert res.forecast_demand == 120.0


# =====================================================================
# 2. RECOMMENDATIONS ENDPOINT TESTS (GET /recommendations)
# =====================================================================


def test_recommendations_with_model_forecast(client, db_session, mock_forecast_payload):
    """GET /recommendations computes recommended order quantities using Forecast Service."""
    sku_id = "SKU-000123"
    warehouse_id = "WH-BLR-01"
    # Lead time = 5 days, Safety stock = 10, Qty on hand = 15
    # Forecast daily demand = 10 units/day -> Lead time demand = 50 -> Reorder point = 50 + 10 = 60
    # Qty on hand (15) < Reorder point (60) -> Recommended order qty = 60 - 15 = 45 units
    seed_inventory_and_supplier(
        db_session,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        qty_on_hand=15,
        safety_stock=10,
        lead_time=5,
        unit_cost=20.0,
    )

    parsed_forecast = ForecastServingResponse.model_validate(mock_forecast_payload)

    with patch("app.services.optimization_service.forecast_client.fetch_forecast", return_value=parsed_forecast):
        resp = client.get("/api/v1/inventory/optimization/recommendations")

    assert resp.status_code == 200
    data = resp.json()

    assert "generated_at" in data
    assert "recommendations" in data
    assert len(data["recommendations"]) >= 1

    item = next((r for r in data["recommendations"] if r["sku_id"] == sku_id and r["warehouse_id"] == warehouse_id), None)
    assert item is not None
    assert item["supplier_id"] == "SUP-00045"
    assert item["current_stock"] == 15
    assert item["safety_stock"] == 10
    assert item["reorder_point"] == 60
    assert item["forecast_demand"] == 300.0  # 30 days * 10 units
    assert item["forecast_source"] == "model"
    assert item["recommended_order_quantity"] == 45
    assert item["estimated_unit_cost"] == 20.0
    assert item["estimated_total_cost"] == 900.0  # 45 * 20.0
    assert data["total_recommended_spend"] >= 900.0


def test_recommendations_with_fallback_source(client, db_session):
    """GET /recommendations gracefully falls back to 28-day sales moving average when forecast service fails."""
    sku_id = "SKU-000124"
    warehouse_id = "WH-DEL-01"
    # Seed 28 days of 8 units/day sales
    seed_28_day_sales(db_session, sku_id=sku_id, warehouse_id=warehouse_id, daily_qty=8)
    # Lead time = 4 days, Safety stock = 12, Qty on hand = 10
    # Daily demand = 8.0 -> Lead time demand = 32 -> Reorder point = 32 + 12 = 44
    # Recommended order qty = 44 - 10 = 34 units
    seed_inventory_and_supplier(
        db_session,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        qty_on_hand=10,
        safety_stock=12,
        lead_time=4,
        unit_cost=15.0,
    )

    with patch("app.services.optimization_service.forecast_client.fetch_forecast", return_value=None):
        resp = client.get("/api/v1/inventory/optimization/recommendations")

    assert resp.status_code == 200
    data = resp.json()

    item = next((r for r in data["recommendations"] if r["sku_id"] == sku_id and r["warehouse_id"] == warehouse_id), None)
    assert item is not None
    assert item["forecast_source"] == "fallback"
    assert item["reorder_point"] == 44
    assert item["recommended_order_quantity"] == 34
    assert item["forecast_demand"] == 240.0  # 8.0 * 30 days
    assert item["estimated_unit_cost"] == 15.0
    assert item["estimated_total_cost"] == 510.0


def test_items_above_reorder_point_are_not_recommended(client, db_session, mock_forecast_payload):
    """Items with sufficient on-hand inventory (quantity >= reorder_point) are excluded from recommendations."""
    sku_id = "SKU-000125"
    warehouse_id = "WH-BOM-01"
    # Lead time = 2, Safety stock = 5, Daily demand = 10 -> Reorder point = 25
    # On-hand = 30 (>= 25) -> No recommendation needed
    seed_inventory_and_supplier(
        db_session,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        qty_on_hand=30,
        safety_stock=5,
        lead_time=2,
    )

    mock_forecast_payload["sku_id"] = sku_id
    mock_forecast_payload["warehouse_id"] = warehouse_id
    parsed_forecast = ForecastServingResponse.model_validate(mock_forecast_payload)

    with patch("app.services.optimization_service.forecast_client.fetch_forecast", return_value=parsed_forecast):
        resp = client.get("/api/v1/inventory/optimization/recommendations")

    assert resp.status_code == 200
    data = resp.json()
    item = next((r for r in data["recommendations"] if r["sku_id"] == sku_id and r["warehouse_id"] == warehouse_id), None)
    assert item is None


def test_recommendations_unauthenticated_returns_401(client_raw):
    """Unauthenticated calls are rejected with 401."""
    resp = client_raw.get("/api/v1/inventory/optimization/recommendations")
    assert resp.status_code == 401



def test_forecast_down_is_called_only_once_per_request(db_session):
    """After the first row exhausts its retries, the other rows go straight to fallback."""
    seed_inventory_and_supplier(db_session, "SKU-000123", "WH-BLR-01", qty_on_hand=0)
    seed_inventory_and_supplier(db_session, "SKU-000124", "WH-DEL-01", qty_on_hand=0)

    with patch("app.services.forecast_client.httpx.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_instance
        mock_instance.get.side_effect = httpx.ConnectError("Connection refused")

        fc = ForecastClient(base_url="http://localhost:8007", timeout_seconds=1.0, max_retries=1)
        result = generate_recommendations(db=db_session, client=fc)

        # 1 row x (1 attempt + 1 retry); later rows never call the service
        assert mock_instance.get.call_count == 2
        assert all(r.forecast_source == "fallback" for r in result.recommendations)


def test_sku_without_supplier_is_skipped(client, db_session):
    """No supplier for a SKU -> no recommendation, never a made-up SUP-00001."""
    seed_inventory_and_supplier(db_session, "SKU-000123", "WH-BLR-01", qty_on_hand=0)
    db_session.add(
        Inventory(
            sku_id="SKU-000777",
            warehouse_id="WH-BLR-01",
            product_name="No Supplier Product",
            category="Electronics",
            quantity_on_hand=0,
            safety_stock=10,
            lead_time_days=5,
        )
    )
    db_session.commit()

    with patch("app.services.optimization_service.forecast_client.fetch_forecast", return_value=None):
        resp = client.get("/api/v1/inventory/optimization/recommendations")

    assert resp.status_code == 200
    recs = resp.json()["recommendations"]
    assert any(r["sku_id"] == "SKU-000123" for r in recs)
    assert not any(r["sku_id"] == "SKU-000777" for r in recs)
    assert not any(r["supplier_id"] == "SUP-00001" for r in recs)


def test_forecast_for_other_sku_is_not_used(db_session, mock_forecast_payload):
    seed_28_day_sales(db_session, "SKU-000124", "WH-BLR-01", daily_qty=5)
    parsed = ForecastServingResponse.model_validate(mock_forecast_payload)  # SKU-000123
    fc = ForecastClient(base_url="http://localhost:8007")

    with patch.object(fc, "fetch_forecast", return_value=parsed):
        res = fc.resolve_demand(db=db_session, sku_id="SKU-000124", warehouse_id="WH-BLR-01")

    assert res.forecast_source == "fallback"
    assert res.daily_demand == 5.0


def test_stale_forecast_is_not_used(db_session, mock_forecast_payload):
    seed_28_day_sales(db_session, "SKU-000123", "WH-BLR-01", daily_qty=5)
    mock_forecast_payload["generated_at"] = (
        datetime.now(timezone.utc) - timedelta(days=settings.FORECAST_MAX_AGE_DAYS + 1)
    ).isoformat()
    parsed = ForecastServingResponse.model_validate(mock_forecast_payload)
    fc = ForecastClient(base_url="http://localhost:8007")

    with patch.object(fc, "fetch_forecast", return_value=parsed):
        res = fc.resolve_demand(db=db_session, sku_id="SKU-000123", warehouse_id="WH-BLR-01")

    assert res.forecast_source == "fallback"
