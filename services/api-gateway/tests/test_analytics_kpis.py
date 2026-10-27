"""
Comprehensive tests for Round 15 Milestone 3:
Analytics KPI Endpoint from ClickHouse and Redis Caching.

Endpoint: GET /api/v1/analytics/kpis
Redis cache key: live_kpis (TTL: 300s)
ClickHouse tables: kpi_metrics, inventory_snapshots, transport_performance
"""

from __future__ import annotations

import json
import re
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
import pytest

from app.core.config import settings
from app.main import app
from app.schemas.analytics import KpiDashboardResponse
from app.services.analytics import AnalyticsKpiService, analytics_kpi_service

CANONICAL_WH_RE = re.compile(r"^WH-[A-Z]{3}-\d{2}$")


def is_optional_count(val: Any) -> bool:
    """Validate that val is either None or a non-negative integer."""
    if val is None:
        return True
    return isinstance(val, int) and not isinstance(val, bool) and val >= 0


def is_optional_non_negative_number(val: Any) -> bool:
    """Validate that val is either None or a non-negative finite number."""
    if val is None:
        return True
    return isinstance(val, (int, float)) and not isinstance(val, bool) and val >= 0


def assert_matches_frontend_contract(data: dict[str, Any]) -> None:
    """
    Validate that a response payload strictly matches the frontend contract
    defined in frontend/packages/dashboard/src/api/kpis.ts (isValidResponse).
    """
    # 1. Top-level envelope
    assert data.get("contract_version") == "v1"
    assert isinstance(data.get("generated_at"), str)
    assert isinstance(data.get("cached"), bool)
    ttl = data.get("cache_ttl_seconds")
    if ttl is not None:
        assert isinstance(ttl, int) and ttl >= 0

    filters = data.get("filters_applied")
    assert isinstance(filters, dict)
    assert isinstance(filters.get("window_days"), int) and filters["window_days"] >= 1
    for k in ("warehouse_id", "category", "start_date", "end_date"):
        assert filters.get(k) is None or isinstance(filters[k], str)

    kpis = data.get("kpis")
    assert isinstance(kpis, dict)

    # 2. Fill Rate
    fill = kpis.get("fill_rate")
    assert isinstance(fill, dict)
    assert isinstance(fill.get("current_rate"), (int, float))
    assert 0.0 <= fill["current_rate"] <= 100.0
    assert isinstance(fill.get("target_rate"), (int, float))
    assert 0.0 <= fill["target_rate"] <= 100.0
    assert is_optional_count(fill.get("total_lines_ordered"))
    assert is_optional_count(fill.get("lines_fulfilled"))
    assert fill.get("status") in ("on_target", "warning", "critical")
    assert fill.get("trend") in ("up", "down", "stable")
    change_pct = fill.get("change_percentage")
    assert change_pct is None or isinstance(change_pct, (int, float))

    # 3. Stockouts
    stockouts = kpis.get("stockouts")
    assert isinstance(stockouts, dict)
    assert isinstance(stockouts.get("total_stockouts"), int) and stockouts["total_stockouts"] >= 0
    assert is_optional_count(stockouts.get("critical_skus"))
    assert is_optional_count(stockouts.get("at_risk_skus"))
    assert stockouts.get("status") in ("normal", "warning", "critical")
    assert stockouts.get("trend") in ("improving", "worsening", "stable")
    assert isinstance(stockouts.get("by_warehouse"), list)
    for wh in stockouts["by_warehouse"]:
        assert isinstance(wh, dict)
        assert isinstance(wh.get("warehouse_id"), str)
        assert CANONICAL_WH_RE.match(wh["warehouse_id"]), f"Invalid WH id: {wh['warehouse_id']}"
        assert isinstance(wh.get("stockout_count"), int) and wh["stockout_count"] >= 0
        assert is_optional_count(wh.get("at_risk_count"))
        assert is_optional_count(wh.get("total_skus"))

    # 4. Open Purchase Orders
    orders = kpis.get("open_purchase_orders")
    assert isinstance(orders, dict)
    assert isinstance(orders.get("total_open_orders"), int) and orders["total_open_orders"] >= 0
    assert is_optional_non_negative_number(orders.get("total_value_usd"))
    assert is_optional_count(orders.get("pending_approval"))
    by_status = orders.get("by_status")
    if by_status is not None:
        assert isinstance(by_status, dict)
        for st in ("draft", "approved", "acknowledged", "in_transit"):
            assert is_optional_count(by_status.get(st))

    # 5. On-Time Delivery
    delivery = kpis.get("on_time_delivery")
    assert isinstance(delivery, dict)
    assert isinstance(delivery.get("current_rate"), (int, float))
    assert 0.0 <= delivery["current_rate"] <= 100.0
    assert isinstance(delivery.get("target_rate"), (int, float))
    assert 0.0 <= delivery["target_rate"] <= 100.0
    assert is_optional_count(delivery.get("total_shipments"))
    assert is_optional_count(delivery.get("delivered_on_time"))
    assert is_optional_count(delivery.get("delayed"))
    assert delivery.get("status") in ("on_target", "warning", "critical")
    assert delivery.get("trend") in ("up", "down", "stable")
    del_change = delivery.get("change_percentage")
    assert del_change is None or isinstance(del_change, (int, float))


# Standard ClickHouse mocked rows
SAMPLE_KPI_ROWS = [
    # (metric_name, metric_date, warehouse_id, category, value, computed_at)
    ("fill_rate", "2026-10-27", "", "", 94.8, "2026-10-27 10:00:00"),
    ("fill_rate", "2026-10-26", "", "", 93.6, "2026-10-26 10:00:00"),
    ("fill_rate", "2026-10-01", "", "", 98.0, "2026-10-01 10:00:00"),
    ("stockout_count", "2026-10-27", "", "", 14.0, "2026-10-27 10:00:00"),
    ("stockout_count", "2026-10-26", "", "", 18.0, "2026-10-26 10:00:00"),
    ("open_pos", "2026-10-27", "", "", 42.0, "2026-10-27 10:00:00"),
    ("on_time_delivery_pct", "2026-10-27", "", "", 92.4, "2026-10-27 10:00:00"),
    ("on_time_delivery_pct", "2026-10-26", "", "", 93.2, "2026-10-26 10:00:00"),
]

SAMPLE_WH_STOCKOUT_ROWS = [
    # (warehouse_id, value, metric_date)
    ("WH-ORD-01", 5.0, "2026-10-27"),
    ("WH-CHI-01", 9.0, "2026-10-27"),
]

SAMPLE_SNAPSHOT_ROWS = [
    # (warehouse_id, total_skus, stockout_count)
    ("WH-ORD-01", 120, 5),
    ("WH-CHI-01", 150, 9),
]

SAMPLE_TRANSPORT_ROWS = [
    # (total_shipments, delivered_on_time, delayed, unknown_count)
    (1250, 1155, 95, 0),
]


class MockQueryResult:
    def __init__(self, rows: list[Any]):
        self.result_rows = rows


@pytest.fixture
def mock_clickhouse_client():
    client = MagicMock()

    def query_side_effect(sql: str, parameters: dict[str, Any] | None = None):
        if "metric_name = 'stockout_count'" in sql and "warehouse_id != ''" in sql:
            return MockQueryResult(SAMPLE_WH_STOCKOUT_ROWS)
        if "inventory_snapshots" in sql:
            return MockQueryResult(SAMPLE_SNAPSHOT_ROWS)
        if "transport_performance" in sql:
            return MockQueryResult(SAMPLE_TRANSPORT_ROWS)
        if "kpi_metrics" in sql:
            return MockQueryResult(SAMPLE_KPI_ROWS)
        return MockQueryResult([])

    client.query.side_effect = query_side_effect
    return client


@pytest.fixture
def mock_redis_client():
    client = AsyncMock()
    # By default, cache miss
    client.get.return_value = None
    client.set.return_value = True
    client.ttl.return_value = 300
    return client


# ---------------------------------------------------------------------------
# 17 Focused Test Scenarios
# ---------------------------------------------------------------------------


def test_1_valid_kpi_response_structure_and_contract_version(mock_clickhouse_client, mock_redis_client):
    """1. Test successful KPI response with all 4 KPIs matching contract v1 and structure."""
    with patch.object(analytics_kpi_service, "get_clickhouse_client", return_value=mock_clickhouse_client), \
         patch.object(analytics_kpi_service, "get_redis_client", return_value=mock_redis_client):
        with TestClient(app) as client:
            response = client.get("/api/v1/analytics/kpis")

        assert response.status_code == 200
        payload = response.json()
        assert_matches_frontend_contract(payload)

        assert payload["contract_version"] == "v1"
        assert payload["cached"] is False
        assert payload["cache_ttl_seconds"] == 300

        kpis = payload["kpis"]
        assert kpis["fill_rate"]["current_rate"] == 94.8
        assert kpis["stockouts"]["total_stockouts"] == 14
        assert kpis["open_purchase_orders"]["total_open_orders"] == 42
        assert kpis["on_time_delivery"]["current_rate"] == 92.4


def test_2_correct_default_filter_behavior(mock_clickhouse_client, mock_redis_client):
    """2. Test default filter behavior (30-day window, no warehouse/category, 'live_kpis' cache key)."""
    with patch.object(analytics_kpi_service, "get_clickhouse_client", return_value=mock_clickhouse_client), \
         patch.object(analytics_kpi_service, "get_redis_client", return_value=mock_redis_client):
        with TestClient(app) as client:
            response = client.get("/api/v1/analytics/kpis")

        assert response.status_code == 200
        payload = response.json()
        filters = payload["filters_applied"]
        assert filters["window_days"] == 30
        assert filters["warehouse_id"] is None
        assert filters["category"] is None
        assert filters["start_date"] is None
        assert filters["end_date"] is None

        # Cache key must strictly be 'live_kpis'
        mock_redis_client.get.assert_called_once_with("live_kpis")


def test_3_warehouse_and_category_filtering(mock_clickhouse_client, mock_redis_client):
    """3. Test warehouse and category filter application and distinct cache key."""
    with patch.object(analytics_kpi_service, "get_clickhouse_client", return_value=mock_clickhouse_client), \
         patch.object(analytics_kpi_service, "get_redis_client", return_value=mock_redis_client):
        with TestClient(app) as client:
            response = client.get("/api/v1/analytics/kpis?warehouse_id=WH-ORD-01&category=industrial")

        assert response.status_code == 200
        payload = response.json()
        filters = payload["filters_applied"]
        assert filters["warehouse_id"] == "WH-ORD-01"
        assert filters["category"] == "industrial"

        # Filtered cache key must reflect dimensions
        expected_key = "live_kpis:WH-ORD-01:industrial:::30"
        mock_redis_client.get.assert_called_once_with(expected_key)

        # ClickHouse queries received parameters
        assert mock_clickhouse_client.query.called
        for call_item in mock_clickhouse_client.query.call_args_list:
            params = call_item[1].get("parameters", {})
            if "warehouse_id" in params:
                assert params["warehouse_id"] == "WH-ORD-01"


def test_4_start_end_date_filtering_and_invalid_date_ranges(mock_clickhouse_client, mock_redis_client):
    """4. Test start/end date filtering and rejection of invalid date ranges or formats."""
    with patch.object(analytics_kpi_service, "get_clickhouse_client", return_value=mock_clickhouse_client), \
         patch.object(analytics_kpi_service, "get_redis_client", return_value=mock_redis_client):
        with TestClient(app) as client:
            # Valid date range
            valid_resp = client.get("/api/v1/analytics/kpis?start_date=2026-10-01&end_date=2026-10-15")
            assert valid_resp.status_code == 200
            data = valid_resp.json()
            assert data["filters_applied"]["start_date"] == "2026-10-01"
            assert data["filters_applied"]["end_date"] == "2026-10-15"
            assert data["filters_applied"]["window_days"] == 14

            # Invalid range: start_date > end_date -> 400 Bad Request
            inverted_resp = client.get("/api/v1/analytics/kpis?start_date=2026-10-25&end_date=2026-10-10")
            assert inverted_resp.status_code == 400
            assert "start_date cannot be after end_date" in inverted_resp.json()["detail"]

            # Malformed date format -> 400 Bad Request
            malformed_resp = client.get("/api/v1/analytics/kpis?start_date=2026/10/01")
            assert malformed_resp.status_code == 400
            assert "YYYY-MM-DD" in malformed_resp.json()["detail"]


def test_5_latest_record_selection_and_no_aggregate_double_counting(mock_redis_client):
    """5. Ensure aggregate KPI rows and warehouse-specific rows are not accidentally double-counted."""
    # Mock ClickHouse containing both national aggregate (empty warehouse) and warehouse-specific rows
    mixed_rows = [
        # (metric_name, metric_date, warehouse_id, category, value, computed_at)
        ("stockout_count", "2026-10-27", "", "", 14.0, "2026-10-27 10:00:00"),
        ("stockout_count", "2026-10-27", "WH-ORD-01", "", 5.0, "2026-10-27 10:00:00"),
        ("stockout_count", "2026-10-27", "WH-CHI-01", "", 9.0, "2026-10-27 10:00:00"),
    ]
    mixed_client = MagicMock()
    mixed_client.query.return_value = MockQueryResult(mixed_rows)

    with patch.object(analytics_kpi_service, "get_clickhouse_client", return_value=mixed_client), \
         patch.object(analytics_kpi_service, "get_redis_client", return_value=mock_redis_client):
        with TestClient(app) as client:
            resp = client.get("/api/v1/analytics/kpis")

        assert resp.status_code == 200
        payload = resp.json()
        # National total stockouts must NOT be 14 + 5 + 9 = 28! It must strictly be the aggregate 14.
        assert payload["kpis"]["stockouts"]["total_stockouts"] == 14


def test_6_trends_using_comparable_periods(mock_redis_client):
    """6. Ensure trend is computed against immediate preceding date, not oldest date in window."""
    # Dates: 2026-10-27 (94.8), 2026-10-26 (93.6), 2026-10-01 (98.0)
    series_rows = [
        ("fill_rate", "2026-10-27", "", "", 94.8, "2026-10-27 10:00:00"),
        ("fill_rate", "2026-10-26", "", "", 93.6, "2026-10-26 10:00:00"),
        ("fill_rate", "2026-10-01", "", "", 98.0, "2026-10-01 10:00:00"),
    ]
    client_mock = MagicMock()
    client_mock.query.return_value = MockQueryResult(series_rows)

    with patch.object(analytics_kpi_service, "get_clickhouse_client", return_value=client_mock), \
         patch.object(analytics_kpi_service, "get_redis_client", return_value=mock_redis_client):
        with TestClient(app) as client:
            resp = client.get("/api/v1/analytics/kpis")

        assert resp.status_code == 200
        fill = resp.json()["kpis"]["fill_rate"]
        # 94.8 vs 93.6 is +1.2% (trend 'up')
        # If it compared with 98.0 (oldest), diff would have been -3.2% (trend 'down')
        assert fill["trend"] == "up"
        assert fill["change_percentage"] == 1.2


def test_7_no_fabricated_fill_rate_counts(mock_clickhouse_client, mock_redis_client):
    """7. Ensure total_lines_ordered and lines_fulfilled are not fabricated."""
    with patch.object(analytics_kpi_service, "get_clickhouse_client", return_value=mock_clickhouse_client), \
         patch.object(analytics_kpi_service, "get_redis_client", return_value=mock_redis_client):
        with TestClient(app) as client:
            resp = client.get("/api/v1/analytics/kpis")

        assert resp.status_code == 200
        fill = resp.json()["kpis"]["fill_rate"]
        assert fill["total_lines_ordered"] is None
        assert fill["lines_fulfilled"] is None


def test_8_no_fabricated_stockout_or_sku_counts(mock_clickhouse_client, mock_redis_client):
    """8. Ensure critical_skus and at_risk_skus are not fabricated, and no minimum SKU floor is forced."""
    with patch.object(analytics_kpi_service, "get_clickhouse_client", return_value=mock_clickhouse_client), \
         patch.object(analytics_kpi_service, "get_redis_client", return_value=mock_redis_client):
        with TestClient(app) as client:
            resp = client.get("/api/v1/analytics/kpis")

        assert resp.status_code == 200
        stock = resp.json()["kpis"]["stockouts"]
        assert stock["critical_skus"] is None
        assert stock["at_risk_skus"] is None

        # Verify real warehouse total_skus is used without max(val, 50) fabrication
        by_wh = stock["by_warehouse"]
        assert len(by_wh) == 2
        assert by_wh[0]["warehouse_id"] == "WH-ORD-01"
        assert by_wh[0]["total_skus"] == 120
        assert by_wh[0]["at_risk_count"] is None


def test_9_no_fabricated_po_status_counts_or_monetary_values(mock_clickhouse_client, mock_redis_client):
    """9. Ensure PO monetary value and status breakdown are not fabricated from fixed ratios."""
    with patch.object(analytics_kpi_service, "get_clickhouse_client", return_value=mock_clickhouse_client), \
         patch.object(analytics_kpi_service, "get_redis_client", return_value=mock_redis_client):
        with TestClient(app) as client:
            resp = client.get("/api/v1/analytics/kpis")

        assert resp.status_code == 200
        orders = resp.json()["kpis"]["open_purchase_orders"]
        assert orders["total_open_orders"] == 42
        assert orders["total_value_usd"] is None
        assert orders["pending_approval"] is None
        assert orders["by_status"] is None


def test_10_unknown_shipment_delivery_status_handling(mock_redis_client):
    """10. Ensure shipments with unknown on_time (NULL) are excluded from rate denominator and not classified as late."""
    # 100 total shipments: 80 on-time, 10 delayed, 10 unknown (on_time is NULL)
    # Denominator must be 80 + 10 = 90. Rate = 80 / 90 * 100 = 88.89%
    unknown_transport_rows = [
        (100, 80, 10, 10),
    ]
    client_mock = MagicMock()

    def query_side_effect(sql: str, parameters: dict[str, Any] | None = None):
        if "transport_performance" in sql:
            return MockQueryResult(unknown_transport_rows)
        return MockQueryResult(SAMPLE_KPI_ROWS)

    client_mock.query.side_effect = query_side_effect

    with patch.object(analytics_kpi_service, "get_clickhouse_client", return_value=client_mock), \
         patch.object(analytics_kpi_service, "get_redis_client", return_value=mock_redis_client):
        with TestClient(app) as client:
            resp = client.get("/api/v1/analytics/kpis")

        assert resp.status_code == 200
        deliv = resp.json()["kpis"]["on_time_delivery"]
        assert deliv["total_shipments"] == 100
        assert deliv["delivered_on_time"] == 80
        assert deliv["delayed"] == 10
        # Rate is 80 / 90 * 100 = 88.89%, NOT 80% (which would happen if unknown was treated as delayed)
        assert deliv["current_rate"] == 88.89


def test_11_shipment_counts_from_real_rows_and_none_when_only_kpi_pct(mock_redis_client):
    """11. Total shipments and counts are None when only percentage metric is available; never fabricated as 100."""
    client_mock = MagicMock()

    def query_side_effect(sql: str, parameters: dict[str, Any] | None = None):
        if "transport_performance" in sql:
            return MockQueryResult([])  # No transport rows
        return MockQueryResult(SAMPLE_KPI_ROWS)

    client_mock.query.side_effect = query_side_effect

    with patch.object(analytics_kpi_service, "get_clickhouse_client", return_value=client_mock), \
         patch.object(analytics_kpi_service, "get_redis_client", return_value=mock_redis_client):
        with TestClient(app) as client:
            resp = client.get("/api/v1/analytics/kpis")

        assert resp.status_code == 200
        deliv = resp.json()["kpis"]["on_time_delivery"]
        # current_rate falls back to historical on_time_delivery_pct in kpi_metrics
        assert deliv["current_rate"] == 92.4
        # But shipment counts are None, NEVER fabricated as 100!
        assert deliv["total_shipments"] is None
        assert deliv["delivered_on_time"] is None
        assert deliv["delayed"] is None


def test_12_redis_caching_hits_misses_ttl_and_key_separation(mock_clickhouse_client, mock_redis_client):
    """12. Test cache miss, cache hit, 300s TTL, and key separation between filter sets."""
    # 1. Cache Miss
    mock_redis_client.get.return_value = None
    with patch.object(analytics_kpi_service, "get_clickhouse_client", return_value=mock_clickhouse_client), \
         patch.object(analytics_kpi_service, "get_redis_client", return_value=mock_redis_client):
        with TestClient(app) as client:
            miss_resp = client.get("/api/v1/analytics/kpis")

        assert miss_resp.status_code == 200
        assert miss_resp.json()["cached"] is False
        assert mock_clickhouse_client.query.called
        assert mock_redis_client.set.called
        assert mock_redis_client.set.call_args[0][0] == "live_kpis"
        assert mock_redis_client.set.call_args[1]["ex"] == 300

    # 2. Cache Hit
    cached_payload = {
        "contract_version": "v1",
        "generated_at": "2026-10-27T10:00:00Z",
        "cached": False,
        "cache_ttl_seconds": 300,
        "filters_applied": {
            "warehouse_id": None,
            "category": None,
            "start_date": None,
            "end_date": None,
            "window_days": 30,
        },
        "kpis": {
            "fill_rate": {
                "current_rate": 96.0,
                "target_rate": 95.0,
                "total_lines_ordered": None,
                "lines_fulfilled": None,
                "status": "on_target",
                "trend": "up",
                "change_percentage": 1.0,
            },
            "stockouts": {
                "total_stockouts": 2,
                "critical_skus": None,
                "at_risk_skus": None,
                "status": "normal",
                "trend": "improving",
                "by_warehouse": [],
            },
            "open_purchase_orders": {
                "total_open_orders": 10,
                "total_value_usd": None,
                "pending_approval": None,
                "by_status": None,
            },
            "on_time_delivery": {
                "current_rate": 98.0,
                "target_rate": 95.0,
                "total_shipments": 200,
                "delivered_on_time": 196,
                "delayed": 4,
                "status": "on_target",
                "trend": "up",
                "change_percentage": 2.0,
            },
        },
    }
    mock_redis_client.get.return_value = json.dumps(cached_payload)
    mock_redis_client.ttl.return_value = 240
    mock_clickhouse_client.query.reset_mock()

    with patch.object(analytics_kpi_service, "get_clickhouse_client", return_value=mock_clickhouse_client), \
         patch.object(analytics_kpi_service, "get_redis_client", return_value=mock_redis_client):
        with TestClient(app) as client:
            hit_resp = client.get("/api/v1/analytics/kpis")

        assert hit_resp.status_code == 200
        payload = hit_resp.json()
        assert payload["cached"] is True
        assert payload["cache_ttl_seconds"] == 240
        assert payload["kpis"]["fill_rate"]["current_rate"] == 96.0
        # ClickHouse was NOT queried
        mock_clickhouse_client.query.assert_not_called()

    # 3. Key separation
    key1 = analytics_kpi_service.get_cache_key(None, None, None, None, 30)
    key2 = analytics_kpi_service.get_cache_key("WH-ORD-01", None, None, None, 30)
    key3 = analytics_kpi_service.get_cache_key(None, "electronics", None, None, 30)
    assert key1 == "live_kpis"
    assert key2 == "live_kpis:WH-ORD-01:all:::30"
    assert key3 == "live_kpis:all:electronics:::30"
    assert len({key1, key2, key3}) == 3


def test_13_redis_failure_fallback_to_clickhouse(mock_clickhouse_client):
    """13. Ensure Redis connection failures gracefully fall back to ClickHouse."""
    broken_redis = AsyncMock()
    broken_redis.get.side_effect = ConnectionError("Redis cluster unreachable")
    broken_redis.set.side_effect = ConnectionError("Redis cluster unreachable")

    with patch.object(analytics_kpi_service, "get_clickhouse_client", return_value=mock_clickhouse_client), \
         patch.object(analytics_kpi_service, "get_redis_client", return_value=broken_redis):
        with TestClient(app) as client:
            resp = client.get("/api/v1/analytics/kpis")

        assert resp.status_code == 200
        payload = resp.json()
        assert_matches_frontend_contract(payload)
        assert payload["cached"] is False
        assert payload["kpis"]["fill_rate"]["current_rate"] == 94.8


def test_14_clickhouse_empty_results_and_database_errors(mock_redis_client):
    """14. Test ClickHouse returning empty rows vs genuine database query errors."""
    # Empty results -> 200 with zero rates/counts and None for missing line/monetary values
    empty_client = MagicMock()
    empty_client.query.return_value = MockQueryResult([])

    with patch.object(analytics_kpi_service, "get_clickhouse_client", return_value=empty_client), \
         patch.object(analytics_kpi_service, "get_redis_client", return_value=mock_redis_client):
        with TestClient(app) as client:
            resp = client.get("/api/v1/analytics/kpis")

        assert resp.status_code == 200
        payload = resp.json()
        assert_matches_frontend_contract(payload)
        assert payload["kpis"]["fill_rate"]["current_rate"] == 0.0
        assert payload["kpis"]["stockouts"]["total_stockouts"] == 0
        assert payload["kpis"]["open_purchase_orders"]["total_open_orders"] == 0
        assert payload["kpis"]["on_time_delivery"]["current_rate"] == 0.0

    # Genuine Database error -> 503 Service Unavailable
    failing_client = MagicMock()
    failing_client.query.side_effect = RuntimeError("ClickHouse connection timeout on 9000")

    with patch.object(analytics_kpi_service, "get_clickhouse_client", return_value=failing_client), \
         patch.object(analytics_kpi_service, "get_redis_client", return_value=mock_redis_client):
        with TestClient(app) as client:
            err_resp = client.get("/api/v1/analytics/kpis")

        assert err_resp.status_code == 503
        assert "unavailable" in err_resp.json()["detail"].lower()


def test_15_authentication_failures_preventing_database_access(mock_clickhouse_client, mock_redis_client):
    """15. Ensure authentication failures abort before accessing ClickHouse."""
    with patch.object(analytics_kpi_service, "get_clickhouse_client", return_value=mock_clickhouse_client), \
         patch.object(analytics_kpi_service, "get_redis_client", return_value=mock_redis_client):

        with patch.object(settings, "AUTH_PRECHECK_ENABLED", True):
            with TestClient(app) as client:
                # 1. No token -> 401
                resp_no_token = client.get("/api/v1/analytics/kpis")
                assert resp_no_token.status_code == 401
                assert resp_no_token.json() == {"detail": "Not authenticated"}
                mock_clickhouse_client.query.assert_not_called()

                # 2. Malformed token -> 401
                resp_bad_token = client.get(
                    "/api/v1/analytics/kpis",
                    headers={"Authorization": "Basic 12345"},
                )
                assert resp_bad_token.status_code == 401
                assert resp_bad_token.json() == {"detail": "Invalid or expired token"}
                mock_clickhouse_client.query.assert_not_called()


@pytest.mark.asyncio
async def test_16_resource_cleanup_during_shutdown():
    """16. Test clean resource shutdown closes Redis connection."""
    service = AnalyticsKpiService()
    mock_redis = AsyncMock()
    service._redis_client = mock_redis

    await service.close()
    mock_redis.aclose.assert_awaited_once()
    assert service._redis_client is None

    # Safe to call multiple times
    await service.close()


def test_17_regression_coverage_existing_gateway_behavior():
    """17. Verify route registration precedence and gateway health endpoint."""
    all_paths = [
        getattr(sub, "path", "")
        for r in app.routes
        for sub in (
            r.original_router.routes
            if hasattr(r, "original_router")
            else (r.routes if hasattr(r, "routes") else [r])
        )
    ]
    assert "/api/v1/analytics/kpis" in all_paths
    assert "/{path:path}" in all_paths
    assert all_paths.index("/api/v1/analytics/kpis") < all_paths.index("/{path:path}")

    # Root endpoint regression
    with TestClient(app) as client:
        root_resp = client.get("/")
        assert root_resp.status_code == 200
        root_data = root_resp.json()
        assert root_data.get("status") == "healthy"

        # Downstream health endpoint regression
        health_resp = client.get("/health")
        assert health_resp.status_code == 200
