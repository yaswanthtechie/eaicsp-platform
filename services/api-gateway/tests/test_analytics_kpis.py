"""
Comprehensive tests for Round 15 Milestone 3:
Analytics KPI Endpoint from ClickHouse and Redis Caching.

Endpoint: GET /api/v1/analytics/kpis
Redis cache key: live_kpis (TTL: 300s)
ClickHouse: kpi_metrics and KPI views (kpi_stockouts_by_warehouse,
kpi_fill_rate_by_warehouse, kpi_open_pos_by_status, kpi_on_time_delivery_by_warehouse)
"""

from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import re
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
import pytest
import yaml

from app.core.config import settings
from app.main import app
from app.services.analytics import AnalyticsKpiService, analytics_kpi_service

CONTRACT = Path(__file__).resolve().parents[3] / "contracts" / "openapi" / "analytics-kpis.yaml"


def assert_matches_contract(payload: dict[str, Any], schema_name: str = "KpiDashboardResponse") -> None:
    schemas = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))["components"]["schemas"]
    schema = {**schemas[schema_name], "components": {"schemas": schemas}}
    errors = [f"{list(e.path)}: {e.message}" for e in Draft202012Validator(schema).iter_errors(payload)]
    assert errors == []


@contextmanager
def kpi_client(ch_client, redis_client):
    with patch.object(analytics_kpi_service, "get_clickhouse_client", return_value=ch_client), \
         patch.object(analytics_kpi_service, "get_redis_client", return_value=redis_client), \
         TestClient(app) as client:
        yield client


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

SAMPLE_STOCKOUT_VIEW_ROWS = [("WH-BLR-01", 6, 500), ("WH-BOM-01", 8, 500)]
SAMPLE_FILL_VIEW_ROWS = [(12500, 11850)]
SAMPLE_PO_VIEW_ROWS = [("approved", 12), ("acknowledged", 14), ("in_transit", 16)]
SAMPLE_OTD_VIEW_ROWS = [(340, 314, 26)]


class MockQueryResult:
    def __init__(self, rows: list[Any]):
        self.result_rows = rows


def route_query(kpi_rows=SAMPLE_KPI_ROWS, **view_overrides):
    views = {
        "kpi_stockouts_by_warehouse": SAMPLE_STOCKOUT_VIEW_ROWS,
        "kpi_fill_rate_by_warehouse": SAMPLE_FILL_VIEW_ROWS,
        "kpi_open_pos_by_status": SAMPLE_PO_VIEW_ROWS,
        "kpi_on_time_delivery_by_warehouse": SAMPLE_OTD_VIEW_ROWS,
        **view_overrides,
    }

    def query_side_effect(sql: str, parameters: dict[str, Any] | None = None):
        for view, rows in views.items():
            if view in sql:
                return MockQueryResult(rows)
        if "kpi_metrics" in sql:
            return MockQueryResult(kpi_rows)
        return MockQueryResult([])

    return query_side_effect


@pytest.fixture
def mock_clickhouse_client():
    client = MagicMock()
    client.query.side_effect = route_query()
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
# Test Scenarios
# ---------------------------------------------------------------------------


def test_1_valid_kpi_response_structure_and_contract_version(mock_clickhouse_client, mock_redis_client):
    """1. Test successful KPI response with all 4 KPIs matching contract v1 and structure."""
    with kpi_client(mock_clickhouse_client, mock_redis_client) as client:
        response = client.get("/api/v1/analytics/kpis")

    assert response.status_code == 200
    payload = response.json()
    assert_matches_contract(payload)

    assert payload["contract_version"] == "v1"
    assert payload["cached"] is False
    assert payload["cache_ttl_seconds"] is None

    kpis = payload["kpis"]
    assert kpis["fill_rate"]["current_rate"] == 94.8
    assert kpis["stockouts"]["total_stockouts"] == 14
    assert kpis["open_purchase_orders"]["total_open_orders"] == 42
    assert kpis["on_time_delivery"]["current_rate"] == 92.4


def test_2_correct_default_filter_behavior(mock_clickhouse_client, mock_redis_client):
    """2. Test default filter behavior (30-day window, no warehouse/category, 'live_kpis' cache key)."""
    with kpi_client(mock_clickhouse_client, mock_redis_client) as client:
        response = client.get("/api/v1/analytics/kpis")

    assert response.status_code == 200
    payload = response.json()
    assert_matches_contract(payload)
    filters = payload["filters_applied"]
    assert filters["window_days"] == 30
    assert filters["warehouse_id"] is None
    assert filters["category"] is None
    assert filters["start_date"] is None
    assert filters["end_date"] is None

    mock_redis_client.get.assert_called_once_with("live_kpis")


def test_3_warehouse_and_category_filtering(mock_clickhouse_client, mock_redis_client):
    """3. Test warehouse and category filter application and distinct cache key."""
    with kpi_client(mock_clickhouse_client, mock_redis_client) as client:
        response = client.get("/api/v1/analytics/kpis?warehouse_id=WH-BLR-01&category=industrial")

    assert response.status_code == 200
    payload = response.json()
    assert_matches_contract(payload)
    filters = payload["filters_applied"]
    assert filters["warehouse_id"] == "WH-BLR-01"
    assert filters["category"] == "industrial"

    expected_key = "live_kpis:WH-BLR-01:industrial:::30"
    mock_redis_client.get.assert_called_once_with(expected_key)

    assert mock_clickhouse_client.query.called
    for call_item in mock_clickhouse_client.query.call_args_list:
        params = call_item[1].get("parameters", {})
        if "warehouse_id" in params:
            assert params["warehouse_id"] == "WH-BLR-01"


def test_4_start_end_date_filtering_and_invalid_date_ranges(mock_clickhouse_client, mock_redis_client):
    """4. Test start/end date filtering and rejection of invalid date ranges or formats."""
    with kpi_client(mock_clickhouse_client, mock_redis_client) as client:
        # Valid date range
        valid_resp = client.get("/api/v1/analytics/kpis?start_date=2026-10-01&end_date=2026-10-15")
        assert valid_resp.status_code == 200
        data = valid_resp.json()
        assert_matches_contract(data)
        assert data["filters_applied"]["start_date"] == "2026-10-01"
        assert data["filters_applied"]["end_date"] == "2026-10-15"
        assert data["filters_applied"]["window_days"] == 14

        # Invalid range: start_date > end_date -> 400 Bad Request
        inverted_resp = client.get("/api/v1/analytics/kpis?start_date=2026-10-25&end_date=2026-10-10")
        assert inverted_resp.status_code == 400
        inv_data = inverted_resp.json()
        assert_matches_contract(inv_data, "ErrorResponse")
        assert "start_date cannot be after end_date" in inv_data["message"]

        # Malformed date format -> 400 Bad Request
        malformed_resp = client.get("/api/v1/analytics/kpis?start_date=2026/10/01")
        assert malformed_resp.status_code == 400
        mal_data = malformed_resp.json()
        assert_matches_contract(mal_data, "ErrorResponse")
        assert "YYYY-MM-DD" in mal_data["message"]


def test_5_latest_record_selection_and_no_aggregate_double_counting(mock_redis_client):
    """5. Ensure aggregate KPI rows and warehouse-specific rows are not accidentally double-counted."""
    mixed_rows = [
        ("stockout_count", "2026-10-27", "", "", 14.0, "2026-10-27 10:00:00"),
        ("stockout_count", "2026-10-27", "WH-BLR-01", "", 5.0, "2026-10-27 10:00:00"),
        ("stockout_count", "2026-10-27", "WH-BOM-01", "", 9.0, "2026-10-27 10:00:00"),
    ]
    ch_client = MagicMock()
    ch_client.query.side_effect = route_query(kpi_rows=mixed_rows)

    with kpi_client(ch_client, mock_redis_client) as client:
        resp = client.get("/api/v1/analytics/kpis")

    assert resp.status_code == 200
    payload = resp.json()
    assert_matches_contract(payload)
    assert payload["kpis"]["stockouts"]["total_stockouts"] == 14


def test_6_trends_using_comparable_periods(mock_redis_client):
    """6. Ensure trend is computed against immediate preceding date, not oldest date in window."""
    series_rows = [
        ("fill_rate", "2026-10-27", "", "", 94.8, "2026-10-27 10:00:00"),
        ("fill_rate", "2026-10-26", "", "", 93.6, "2026-10-26 10:00:00"),
        ("fill_rate", "2026-10-01", "", "", 98.0, "2026-10-01 10:00:00"),
    ]
    ch_client = MagicMock()
    ch_client.query.side_effect = route_query(kpi_rows=series_rows)

    with kpi_client(ch_client, mock_redis_client) as client:
        resp = client.get("/api/v1/analytics/kpis")

    assert resp.status_code == 200
    payload = resp.json()
    assert_matches_contract(payload)
    fill = payload["kpis"]["fill_rate"]
    assert fill["trend"] == "up"
    assert fill["change_percentage"] == 1.2


def test_7_no_fabricated_fill_rate_counts(mock_clickhouse_client, mock_redis_client):
    """7. Ensure total_lines_ordered and lines_fulfilled come from the view numbers."""
    with kpi_client(mock_clickhouse_client, mock_redis_client) as client:
        resp = client.get("/api/v1/analytics/kpis")

    assert resp.status_code == 200
    payload = resp.json()
    assert_matches_contract(payload)
    fill = payload["kpis"]["fill_rate"]
    assert fill["total_lines_ordered"] == 12500
    assert fill["lines_fulfilled"] == 11850


def test_8_no_fabricated_stockout_or_sku_counts(mock_clickhouse_client, mock_redis_client):
    """8. Ensure critical_skus and at_risk_skus are null without a source, and view numbers are used."""
    with kpi_client(mock_clickhouse_client, mock_redis_client) as client:
        resp = client.get("/api/v1/analytics/kpis")

    assert resp.status_code == 200
    payload = resp.json()
    assert_matches_contract(payload)
    stock = payload["kpis"]["stockouts"]
    assert stock["critical_skus"] is None
    assert stock["at_risk_skus"] is None

    by_wh = stock["by_warehouse"]
    assert len(by_wh) == 2
    assert by_wh[0]["warehouse_id"] == "WH-BLR-01"
    assert by_wh[0]["stockout_count"] == 6
    assert by_wh[0]["at_risk_count"] is None
    assert by_wh[0]["total_skus"] == 500


def test_9_no_fabricated_po_status_counts_or_monetary_values(mock_clickhouse_client, mock_redis_client):
    """9. Ensure PO monetary value and status breakdown match contract and views."""
    with kpi_client(mock_clickhouse_client, mock_redis_client) as client:
        resp = client.get("/api/v1/analytics/kpis")

    assert resp.status_code == 200
    payload = resp.json()
    assert_matches_contract(payload)
    orders = payload["kpis"]["open_purchase_orders"]
    assert orders["total_open_orders"] == 42
    assert orders["total_value_usd"] is None
    assert orders["pending_approval"] is None
    assert orders["by_status"] == {
        "draft": None,
        "approved": 12,
        "acknowledged": 14,
        "in_transit": 16,
    }


def test_12_redis_caching_hits_misses_ttl_and_key_separation(mock_clickhouse_client, mock_redis_client):
    """12. Test cache miss, cache hit, 300s TTL, and key separation between filter sets."""
    # 1. Cache Miss
    mock_redis_client.get.return_value = None
    with kpi_client(mock_clickhouse_client, mock_redis_client) as client:
        miss_resp = client.get("/api/v1/analytics/kpis")

    assert miss_resp.status_code == 200
    assert miss_resp.json()["cached"] is False
    assert miss_resp.json()["cache_ttl_seconds"] is None
    assert mock_clickhouse_client.query.called
    assert mock_redis_client.set.called
    assert mock_redis_client.set.call_args[0][0] == "live_kpis"
    assert mock_redis_client.set.call_args[1]["ex"] == 300

    # 2. Cache Hit
    cached_payload = {
        "contract_version": "v1",
        "generated_at": "2026-10-27T10:00:00Z",
        "cached": False,
        "cache_ttl_seconds": None,
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
                "total_lines_ordered": 12500,
                "lines_fulfilled": 12000,
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
                "by_status": {
                    "draft": None,
                    "approved": 4,
                    "acknowledged": 3,
                    "in_transit": 3,
                },
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

    with kpi_client(mock_clickhouse_client, mock_redis_client) as client:
        hit_resp = client.get("/api/v1/analytics/kpis")

    assert hit_resp.status_code == 200
    payload = hit_resp.json()
    assert payload["cached"] is True
    assert payload["cache_ttl_seconds"] == 240
    assert payload["kpis"]["fill_rate"]["current_rate"] == 96.0
    mock_clickhouse_client.query.assert_not_called()


def test_13_redis_failure_fallback_to_clickhouse(mock_clickhouse_client):
    """13. Ensure Redis connection failures gracefully fall back to ClickHouse."""
    broken_redis = AsyncMock()
    broken_redis.get.side_effect = ConnectionError("Redis cluster unreachable")
    broken_redis.set.side_effect = ConnectionError("Redis cluster unreachable")

    with kpi_client(mock_clickhouse_client, broken_redis) as client:
        resp = client.get("/api/v1/analytics/kpis")

    assert resp.status_code == 200
    payload = resp.json()
    assert_matches_contract(payload)
    assert payload["cached"] is False
    assert payload["kpis"]["fill_rate"]["current_rate"] == 94.8


def test_14_clickhouse_empty_results_and_database_errors(mock_redis_client):
    """14. Test ClickHouse returning empty rows vs genuine database query errors."""
    empty_client = MagicMock()
    empty_client.query.side_effect = route_query(kpi_rows=[])

    with kpi_client(empty_client, mock_redis_client) as client:
        resp = client.get("/api/v1/analytics/kpis")

    assert resp.status_code == 200
    payload = resp.json()
    assert_matches_contract(payload)
    assert payload["kpis"]["fill_rate"]["current_rate"] is None
    assert payload["kpis"]["stockouts"]["total_stockouts"] == 14
    assert payload["kpis"]["open_purchase_orders"]["total_open_orders"] == 42
    assert payload["kpis"]["on_time_delivery"]["current_rate"] is None

    # Genuine Database error -> 503 Service Unavailable
    failing_client = MagicMock()
    failing_client.query.side_effect = RuntimeError("ClickHouse connection timeout on 9000")

    with kpi_client(failing_client, mock_redis_client) as client:
        err_resp = client.get("/api/v1/analytics/kpis")

    assert err_resp.status_code == 503
    err_body = err_resp.json()
    assert err_body["error_code"] == "SERVICE_UNAVAILABLE"
    assert_matches_contract(err_body, "ErrorResponse")


def test_15_authentication_failures_preventing_database_access(mock_clickhouse_client, mock_redis_client):
    """15. Ensure authentication failures abort before accessing ClickHouse."""
    with patch.object(settings, "AUTH_PRECHECK_ENABLED", True):
        with kpi_client(mock_clickhouse_client, mock_redis_client) as client:
            resp_no_token = client.get("/api/v1/analytics/kpis")
            assert resp_no_token.status_code == 401
            assert resp_no_token.json() == {"detail": "Not authenticated"}
            mock_clickhouse_client.query.assert_not_called()

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

    with TestClient(app) as client:
        root_resp = client.get("/")
        assert root_resp.status_code == 200
        root_data = root_resp.json()
        assert root_data.get("status") == "healthy"

        health_resp = client.get("/health")
        assert health_resp.status_code == 200


def test_counts_come_from_kpi_views(mock_clickhouse_client, mock_redis_client):
    with kpi_client(mock_clickhouse_client, mock_redis_client) as client:
        payload = client.get("/api/v1/analytics/kpis").json()
        assert_matches_contract(payload)
        kpis = payload["kpis"]
        assert (kpis["fill_rate"]["total_lines_ordered"], kpis["fill_rate"]["lines_fulfilled"]) == (12500, 11850)
        assert (kpis["on_time_delivery"]["total_shipments"], kpis["on_time_delivery"]["delayed"]) == (340, 26)
        assert kpis["open_purchase_orders"]["by_status"] == {
            "draft": None,
            "approved": 12,
            "acknowledged": 14,
            "in_transit": 16,
        }
        assert kpis["stockouts"]["by_warehouse"][0] == {
            "warehouse_id": "WH-BLR-01",
            "stockout_count": 6,
            "at_risk_count": None,
            "total_skus": 500,
        }


def test_low_rate_is_not_rescaled(mock_redis_client):
    ch = MagicMock()
    ch.query.side_effect = route_query(
        kpi_rows=[("fill_rate", "2026-10-27", "", "", 0.8, "2026-10-27 10:00:00")]
    )
    with kpi_client(ch, mock_redis_client) as client:
        fill = client.get("/api/v1/analytics/kpis").json()["kpis"]["fill_rate"]
        assert fill["current_rate"] == 0.8
        assert fill["status"] == "critical"


def test_no_rate_rows_return_null_not_zero(mock_redis_client):
    ch = MagicMock()
    ch.query.side_effect = route_query(kpi_rows=[])
    with kpi_client(ch, mock_redis_client) as client:
        payload = client.get("/api/v1/analytics/kpis").json()
        assert_matches_contract(payload)
        for kpi in ("fill_rate", "on_time_delivery"):
            assert payload["kpis"][kpi]["current_rate"] is None
            assert payload["kpis"][kpi]["status"] == "no_data"


def test_view_failure_returns_503_and_is_not_cached(mock_redis_client):
    ok = route_query()

    def failing(sql, parameters=None):
        if "kpi_on_time_delivery_by_warehouse" in sql:
            raise RuntimeError("ClickHouse timeout")
        return ok(sql, parameters)

    ch = MagicMock()
    ch.query.side_effect = failing
    with kpi_client(ch, mock_redis_client) as client:
        resp = client.get("/api/v1/analytics/kpis")
        assert resp.status_code == 503
        assert resp.json()["error_code"] == "SERVICE_UNAVAILABLE"
        assert_matches_contract(resp.json(), "ErrorResponse")
        mock_redis_client.set.assert_not_called()


@pytest.mark.parametrize(
    "query, parameter",
    [
        ("warehouse_id=WH-1", "warehouse_id"),
        ("window_days=0", "window_days"),
        ("window_days=366", "window_days"),
        ("window_days=abc", "window_days"),
        ("start_date=2026/10/01", "start_date"),
        ("category=" + "x" * 65, "category"),
    ],
)
def test_invalid_parameters_return_contract_400(mock_clickhouse_client, mock_redis_client, query, parameter):
    with kpi_client(mock_clickhouse_client, mock_redis_client) as client:
        resp = client.get(f"/api/v1/analytics/kpis?{query}")
        assert resp.status_code == 400
        body = resp.json()
        assert body["error_code"] == "INVALID_PARAMETER"
        assert body["details"]["parameter"] == parameter
        assert_matches_contract(body, "ErrorResponse")
        mock_clickhouse_client.query.assert_not_called()


def test_force_refresh_skips_cache_read(mock_clickhouse_client, mock_redis_client):
    mock_redis_client.get.return_value = json.dumps({"stale": True})
    with kpi_client(mock_clickhouse_client, mock_redis_client) as client:
        payload = client.get("/api/v1/analytics/kpis?force_refresh=true").json()
        assert payload["cached"] is False
        assert payload["cache_ttl_seconds"] is None
        mock_redis_client.get.assert_not_called()
        mock_redis_client.set.assert_called_once()


def test_totals_come_from_views_even_with_a_category_filter(mock_redis_client):
    ch = MagicMock()
    ch.query.side_effect = route_query(kpi_rows=[])
    with kpi_client(ch, mock_redis_client) as client:
        payload = client.get(
            "/api/v1/analytics/kpis?category=industrial"
        ).json()

    assert_matches_contract(payload)

    stockouts = payload["kpis"]["stockouts"]
    orders = payload["kpis"]["open_purchase_orders"]

    assert stockouts["total_stockouts"] == 14
    assert stockouts["status"] == "warning"
    assert orders["total_open_orders"] == sum(
        orders["by_status"][s]
        for s in ("approved", "acknowledged", "in_transit")
    ) == 42
