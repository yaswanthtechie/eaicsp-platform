"""
Analytics KPI service for ClickHouse querying and Redis caching.

Retrieves and computes live KPI metrics for the analytics dashboard:
1. Fill Rate (fill_rate)
2. Inventory Stockouts (stockouts)
3. Open Purchase Orders (open_purchase_orders)
4. Logistics On-Time Delivery (on_time_delivery)

Strictly adheres to:
- contracts/clickhouse/README.md schemas
- No synthetic or invented business metrics
- Deterministic latest-record selection and proper trend comparison periods
- Non-blocking asynchronous execution via worker threads
- Redis caching with graceful degradation and 'live_kpis' default key
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
import re
from typing import Any, Callable

from fastapi import HTTPException
import redis.asyncio as aioredis

from app.core.config import settings
from app.schemas.analytics import (
    FillRateKpi,
    FiltersApplied,
    KpiDashboardResponse,
    KpisPayload,
    OnTimeDeliveryKpi,
    OpenPurchaseOrdersKpi,
    POByStatus,
    StockoutsKpi,
    WarehouseStockout,
)

logger = logging.getLogger("api_gateway.analytics")

# Canonical warehouse identifier regex per contract: WH-[A-Z]{3}-\\d{2}
CANONICAL_WAREHOUSE_RE = re.compile(r"^WH-[A-Z]{3}-\d{2}$")


class AnalyticsKpiService:
    """
    Analytics service that coordinates ClickHouse queries and Redis caching.
    """

    def __init__(
        self,
        redis_client: aioredis.Redis | None = None,
        clickhouse_client_factory: Callable[[], Any] | None = None,
    ):
        self._redis_client = redis_client
        self._ch_client: Any = None
        self._clickhouse_client_factory = clickhouse_client_factory

    def get_redis_client(self) -> aioredis.Redis:
        """
        Get or initialize the asynchronous Redis client.
        """
        if self._redis_client is None:
            self._redis_client = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
            )
        return self._redis_client

    def get_clickhouse_client(self) -> Any:
        """
        Get or initialize a ClickHouse client.
        """
        if self._clickhouse_client_factory is not None:
            return self._clickhouse_client_factory()

        import clickhouse_connect

        return clickhouse_connect.get_client(
            host=settings.CLICKHOUSE_HOST,
            port=settings.CLICKHOUSE_PORT,
            username=settings.CLICKHOUSE_USER,
            password=settings.CLICKHOUSE_PASSWORD,
            database=settings.CLICKHOUSE_DB,
            connect_timeout=5,
            send_receive_timeout=15,
        )

    def _resolve_cache_key(
        self,
        warehouse_id: str | None,
        category: str | None,
        start_date: str | None,
        end_date: str | None,
        window_days: int,
    ) -> str:
        """
        Resolve Redis cache key.
        When no custom filters are applied, the key is strictly 'live_kpis'.
        When filters are applied, all dimensions are included to avoid stale/cross-filter cache hits.
        """
        if not warehouse_id and not category and not start_date and not end_date and window_days == 30:
            return "live_kpis"

        parts = [
            "live_kpis",
            warehouse_id or "all",
            category or "all",
            start_date or "",
            end_date or "",
            str(window_days),
        ]
        return ":".join(parts)

    def get_cache_key(
        self,
        warehouse_id: str | None,
        category: str | None,
        start_date: str | None,
        end_date: str | None,
        window_days: int,
    ) -> str:
        """Public alias for resolving Redis cache key."""
        return self._resolve_cache_key(
            warehouse_id=warehouse_id,
            category=category,
            start_date=start_date,
            end_date=end_date,
            window_days=window_days,
        )

    async def close(self) -> None:
        """
        Clean up Redis and ClickHouse resources on application shutdown.
        """
        redis_client = getattr(self, "_redis_client", None)
        if redis_client is not None:
            try:
                if hasattr(redis_client, "aclose"):
                    await redis_client.aclose()
                elif hasattr(redis_client, "close"):
                    res = redis_client.close()
                    if asyncio.iscoroutine(res):
                        await res
            except Exception as exc:
                logger.debug("Error closing Redis client: %s", exc)
            finally:
                self._redis_client = None

        ch_client = getattr(self, "_ch_client", None)
        if ch_client is not None:
            try:
                if hasattr(ch_client, "close"):
                    ch_client.close()
            except Exception as exc:
                logger.debug("Error closing ClickHouse client: %s", exc)
            finally:
                self._ch_client = None

    async def _get_from_cache(self, cache_key: str) -> dict[str, Any] | None:
        """
        Retrieve cached KPI payload from Redis.
        Gracefully handles Redis connection and timeout errors.
        """
        try:
            client = self.get_redis_client()
            cached_data = await client.get(cache_key)
            if cached_data is not None:
                parsed = json.loads(cached_data)
                ttl = await client.ttl(cache_key)
                parsed["cached"] = True
                parsed["cache_ttl_seconds"] = (
                    ttl if ttl and ttl > 0 else settings.LIVE_KPIS_CACHE_TTL_SECONDS
                )
                logger.info("Redis cache hit for key '%s'", cache_key)
                return parsed
        except Exception as exc:
            logger.warning(
                "Redis cache get failed for key '%s' (falling back to database): %s",
                cache_key,
                exc,
            )
        return None

    async def _save_to_cache(
        self,
        cache_key: str,
        response_dict: dict[str, Any],
        ttl_seconds: int,
    ) -> None:
        """
        Save KPI response payload to Redis cache with the configured TTL.
        Gracefully handles Redis errors without failing the request.
        """
        try:
            client = self.get_redis_client()
            payload_to_cache = dict(response_dict)
            payload_to_cache["cached"] = True
            payload_to_cache["cache_ttl_seconds"] = ttl_seconds
            serialized = json.dumps(payload_to_cache)
            await client.set(cache_key, serialized, ex=ttl_seconds)
            logger.debug(
                "Saved KPI response to Redis cache key '%s' with TTL %ds",
                cache_key,
                ttl_seconds,
            )
        except Exception as exc:
            logger.warning(
                "Failed to write KPI response to Redis cache key '%s': %s",
                cache_key,
                exc,
            )

    def _query_clickhouse_sync(
        self,
        warehouse_id: str | None,
        category: str | None,
        start_date: str | None,
        end_date: str | None,
        window_days: int,
    ) -> dict[str, Any]:
        """
        Synchronous database queries against ClickHouse.
        Must be executed in a separate worker thread to avoid blocking the async event loop.
        """
        client = self.get_clickhouse_client()

        # Resolve date boundaries
        eff_end_date = end_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if start_date:
            eff_start_date = start_date
        else:
            eff_start_date = (
                datetime.strptime(eff_end_date, "%Y-%m-%d").date() - timedelta(days=window_days)
            ).strftime("%Y-%m-%d")

        wh_filter = warehouse_id or ""
        cat_filter = category or ""

        # 1. Query kpi_metrics (primary table)
        kpi_metrics_sql = """
        SELECT
            metric_name,
            metric_date,
            warehouse_id,
            category,
            value,
            computed_at
        FROM kpi_metrics FINAL
        WHERE metric_name IN ('fill_rate', 'stockout_count', 'open_pos', 'on_time_delivery_pct')
          AND (%(warehouse_id)s = '' OR warehouse_id = %(warehouse_id)s)
          AND (%(category)s = '' OR category = %(category)s)
          AND metric_date >= %(start_date)s
          AND metric_date <= %(end_date)s
        ORDER BY metric_date DESC, computed_at DESC
        """

        kpi_rows: list[Any] = []
        try:
            result = client.query(
                kpi_metrics_sql,
                parameters={
                    "warehouse_id": wh_filter,
                    "category": cat_filter,
                    "start_date": eff_start_date,
                    "end_date": eff_end_date,
                },
            )
            kpi_rows = result.result_rows if hasattr(result, "result_rows") else (result or [])
        except Exception as exc:
            logger.error("ClickHouse query error on kpi_metrics: %s", exc)
            raise

        # 2. Query warehouse-level stockout counts from kpi_metrics
        # Only select warehouse rows (warehouse_id != '')
        wh_stockouts_sql = """
        SELECT
            warehouse_id,
            value,
            metric_date
        FROM kpi_metrics FINAL
        WHERE metric_name = 'stockout_count'
          AND warehouse_id != ''
          AND (%(warehouse_id)s = '' OR warehouse_id = %(warehouse_id)s)
          AND (%(category)s = '' OR category = %(category)s)
          AND metric_date >= %(start_date)s
          AND metric_date <= %(end_date)s
        ORDER BY metric_date DESC, computed_at DESC
        """
        wh_kpi_rows: list[Any] = []
        try:
            wh_result = client.query(
                wh_stockouts_sql,
                parameters={
                    "warehouse_id": wh_filter,
                    "category": cat_filter,
                    "start_date": eff_start_date,
                    "end_date": eff_end_date,
                },
            )
            wh_kpi_rows = wh_result.result_rows if hasattr(wh_result, "result_rows") else (wh_result or [])
        except Exception as exc:
            logger.debug("ClickHouse query on warehouse stockouts notice: %s", exc)

        # 3. Query inventory_snapshots for the single latest snapshot_date within range
        # Note: inventory_snapshots does NOT have category column
        snapshot_rows: list[Any] = []
        try:
            snapshot_sql = """
            SELECT
                warehouse_id,
                count(DISTINCT sku_id) as total_skus,
                countIf(quantity_on_hand <= 0) as stockout_count
            FROM inventory_snapshots FINAL
            WHERE snapshot_date = (
                SELECT max(snapshot_date)
                FROM inventory_snapshots FINAL
                WHERE snapshot_date >= %(start_date)s
                  AND snapshot_date <= %(end_date)s
                  AND (%(warehouse_id)s = '' OR warehouse_id = %(warehouse_id)s)
            )
              AND (%(warehouse_id)s = '' OR warehouse_id = %(warehouse_id)s)
            GROUP BY warehouse_id
            ORDER BY warehouse_id
            """
            s_result = client.query(
                snapshot_sql,
                parameters={
                    "warehouse_id": wh_filter,
                    "start_date": eff_start_date,
                    "end_date": eff_end_date,
                },
            )
            snapshot_rows = s_result.result_rows if hasattr(s_result, "result_rows") else (s_result or [])
        except Exception as exc:
            logger.debug("inventory_snapshots query notice: %s", exc)

        # 4. Query transport_performance for actual shipment counts within range
        # Filter on toDate(dispatched_at); transport_performance does NOT have category column
        transport_data: dict[str, Any] = {}
        try:
            transport_sql = """
            SELECT
                count() as total_shipments,
                countIf(on_time = 1) as delivered_on_time,
                countIf(on_time = 0) as delayed,
                countIf(on_time IS NULL) as unknown_count
            FROM transport_performance FINAL
            WHERE toDate(dispatched_at) >= %(start_date)s
              AND toDate(dispatched_at) <= %(end_date)s
              AND (%(warehouse_id)s = '' OR warehouse_id = %(warehouse_id)s)
            """
            t_result = client.query(
                transport_sql,
                parameters={
                    "warehouse_id": wh_filter,
                    "start_date": eff_start_date,
                    "end_date": eff_end_date,
                },
            )
            t_rows = t_result.result_rows if hasattr(t_result, "result_rows") else (t_result or [])
            if t_rows and len(t_rows[0]) >= 4 and t_rows[0][0] > 0:
                tot = int(t_rows[0][0])
                ontime = int(t_rows[0][1])
                late = int(t_rows[0][2])
                known = ontime + late
                rate = round((ontime * 100.0) / known, 2) if known > 0 else 0.0
                transport_data = {
                    "total_shipments": tot,
                    "delivered_on_time": ontime,
                    "delayed": late,
                    "known_shipments": known,
                    "current_rate": rate,
                }
        except Exception as exc:
            logger.debug("transport_performance query notice: %s", exc)

        return {
            "kpi_rows": kpi_rows,
            "wh_kpi_rows": wh_kpi_rows,
            "snapshot_rows": snapshot_rows,
            "transport_data": transport_data,
        }

    def _extract_metric_series(
        self,
        rows: list[Any],
        metric_name: str,
        warehouse_id: str | None,
        category: str | None,
    ) -> dict[str, float]:
        """
        Extract a time-series dict of {metric_date: value} for a given metric.
        Handles aggregate vs warehouse rows correctly without double-counting.
        """
        # Filter rows for this metric
        metric_rows = [r for r in rows if len(r) >= 5 and str(r[0]) == metric_name]
        if not metric_rows:
            return {}

        # Group by date
        by_date: dict[str, list[dict[str, Any]]] = {}
        for r in metric_rows:
            m_date = str(r[1])
            wh = str(r[2]) if r[2] is not None else ""
            cat = str(r[3]) if r[3] is not None else ""
            val = float(r[4]) if r[4] is not None else 0.0
            by_date.setdefault(m_date, []).append({"wh": wh, "cat": cat, "val": val})

        series: dict[str, float] = {}
        for m_date, items in by_date.items():
            if warehouse_id:
                # Warehouse is explicitly requested
                wh_items = [it for it in items if it["wh"] == warehouse_id]
                if not wh_items:
                    continue
                if category:
                    cat_items = [it for it in wh_items if it["cat"] == category]
                    if cat_items:
                        series[m_date] = cat_items[0]["val"]
                else:
                    # Prefer all-category row (cat == '')
                    cat_total = [it for it in wh_items if it["cat"] == ""]
                    if cat_total:
                        series[m_date] = cat_total[0]["val"]
                    else:
                        # Otherwise sum or average across categories
                        if metric_name in ("fill_rate", "on_time_delivery_pct"):
                            series[m_date] = sum(it["val"] for it in wh_items) / len(wh_items)
                        else:
                            series[m_date] = sum(it["val"] for it in wh_items)
            else:
                # Warehouse is NOT specified: look for all-warehouse aggregate (wh == '')
                agg_items = [it for it in items if it["wh"] == ""]
                if agg_items:
                    if category:
                        cat_items = [it for it in agg_items if it["cat"] == category]
                        if cat_items:
                            series[m_date] = cat_items[0]["val"]
                    else:
                        cat_total = [it for it in agg_items if it["cat"] == ""]
                        if cat_total:
                            series[m_date] = cat_total[0]["val"]
                        else:
                            if metric_name in ("fill_rate", "on_time_delivery_pct"):
                                series[m_date] = sum(it["val"] for it in agg_items) / len(agg_items)
                            else:
                                series[m_date] = sum(it["val"] for it in agg_items)
                else:
                    # No aggregate row exists: aggregate ONLY warehouse rows (wh != '')
                    # This ensures aggregate and warehouse rows are NEVER double counted!
                    wh_only_items = [it for it in items if it["wh"] != ""]
                    if wh_only_items:
                        if category:
                            cat_wh_items = [it for it in wh_only_items if it["cat"] == category]
                            if cat_wh_items:
                                if metric_name in ("fill_rate", "on_time_delivery_pct"):
                                    series[m_date] = sum(it["val"] for it in cat_wh_items) / len(cat_wh_items)
                                else:
                                    series[m_date] = sum(it["val"] for it in cat_wh_items)
                        else:
                            cat_total_wh = [it for it in wh_only_items if it["cat"] == ""]
                            targets = cat_total_wh if cat_total_wh else wh_only_items
                            if metric_name in ("fill_rate", "on_time_delivery_pct"):
                                series[m_date] = sum(it["val"] for it in targets) / len(targets)
                            else:
                                series[m_date] = sum(it["val"] for it in targets)

        return series

    def _build_kpi_response(
        self,
        db_results: dict[str, Any],
        warehouse_id: str | None,
        category: str | None,
        start_date: str | None,
        end_date: str | None,
        window_days: int,
    ) -> KpiDashboardResponse:
        """
        Assemble the response model strictly complying with contract_version 'v1'.
        Never uses synthetic/fabricated values.
        """
        kpi_rows = db_results.get("kpi_rows", [])
        wh_kpi_rows = db_results.get("wh_kpi_rows", [])
        snapshot_rows = db_results.get("snapshot_rows", [])
        transport_data = db_results.get("transport_data", {})

        # --- 1. Fill Rate ---
        fill_series = self._extract_metric_series(kpi_rows, "fill_rate", warehouse_id, category)
        target_fill_rate = 95.0
        fill_current_rate = 0.0
        fill_trend: str = "stable"
        fill_change_pct: float | None = None

        if fill_series:
            sorted_dates = sorted(fill_series.keys(), reverse=True)
            raw_fill = fill_series[sorted_dates[0]]
            if 0.0 < raw_fill <= 1.0:
                raw_fill = raw_fill * 100.0
            fill_current_rate = min(100.0, max(0.0, round(raw_fill, 2)))

            # Compare with immediate preceding period
            if len(sorted_dates) > 1:
                prev_raw = fill_series[sorted_dates[1]]
                if 0.0 < prev_raw <= 1.0:
                    prev_raw = prev_raw * 100.0
                prev_fill = min(100.0, max(0.0, round(prev_raw, 2)))
                diff = round(fill_current_rate - prev_fill, 2)
                fill_change_pct = diff
                if diff > 0.05:
                    fill_trend = "up"
                elif diff < -0.05:
                    fill_trend = "down"

        if fill_current_rate >= target_fill_rate:
            fill_status = "on_target"
        elif fill_current_rate >= (target_fill_rate - 5.0):
            fill_status = "warning"
        else:
            fill_status = "critical"

        # Do not fabricate total_lines_ordered or lines_fulfilled
        fill_kpi = FillRateKpi(
            current_rate=fill_current_rate,
            target_rate=target_fill_rate,
            total_lines_ordered=None,
            lines_fulfilled=None,
            status=fill_status,
            trend=fill_trend,  # type: ignore[arg-type]
            change_percentage=fill_change_pct,
        )

        # --- 2. Inventory Stockouts ---
        stockout_series = self._extract_metric_series(kpi_rows, "stockout_count", warehouse_id, category)
        total_stockouts = 0
        stockout_trend: str = "stable"

        if stockout_series:
            sorted_dates = sorted(stockout_series.keys(), reverse=True)
            total_stockouts = int(round(stockout_series[sorted_dates[0]]))
            if len(sorted_dates) > 1:
                prev_val = stockout_series[sorted_dates[1]]
                if total_stockouts < prev_val:
                    stockout_trend = "improving"
                elif total_stockouts > prev_val:
                    stockout_trend = "worsening"

        if total_stockouts == 0:
            stockouts_status = "normal"
        elif total_stockouts <= 20:
            stockouts_status = "warning"
        else:
            stockouts_status = "critical"

        # Build by_warehouse breakdown from real sources without synthetic SKU counts
        by_warehouse_list: list[WarehouseStockout] = []
        seen_warehouses: set[str] = set()

        # Prioritize real snapshot rows from inventory_snapshots (from latest snapshot date)
        for s_row in snapshot_rows:
            if len(s_row) >= 3:
                wh_id = str(s_row[0])
                if CANONICAL_WAREHOUSE_RE.match(wh_id) and wh_id not in seen_warehouses:
                    seen_warehouses.add(wh_id)
                    tot_skus = max(0, int(s_row[1]))
                    st_count = max(0, int(s_row[2]))
                    by_warehouse_list.append(
                        WarehouseStockout(
                            warehouse_id=wh_id,
                            stockout_count=st_count,
                            at_risk_count=None,
                            total_skus=tot_skus,
                        )
                    )

        # Supplement with warehouse rows from kpi_metrics if not already in list
        if wh_kpi_rows:
            # Find latest metric date among wh_kpi_rows
            latest_wh_date = str(wh_kpi_rows[0][2]) if len(wh_kpi_rows[0]) >= 3 else None
            for row in wh_kpi_rows:
                if len(row) >= 2:
                    wh_id = str(row[0])
                    row_date = str(row[2]) if len(row) >= 3 else None
                    if latest_wh_date and row_date != latest_wh_date:
                        continue
                    if CANONICAL_WAREHOUSE_RE.match(wh_id) and wh_id not in seen_warehouses:
                        seen_warehouses.add(wh_id)
                        st_count = max(0, int(round(float(row[1]))))
                        by_warehouse_list.append(
                            WarehouseStockout(
                                warehouse_id=wh_id,
                                stockout_count=st_count,
                                at_risk_count=None,
                                total_skus=None,
                            )
                        )

        # Do not fabricate critical_skus or at_risk_skus without verified source
        stockouts_kpi = StockoutsKpi(
            total_stockouts=total_stockouts,
            critical_skus=None,
            at_risk_skus=None,
            status=stockouts_status,  # type: ignore[arg-type]
            trend=stockout_trend,  # type: ignore[arg-type]
            by_warehouse=by_warehouse_list,
        )

        # --- 3. Open Purchase Orders ---
        po_series = self._extract_metric_series(kpi_rows, "open_pos", warehouse_id, category)
        total_open_orders = 0
        if po_series:
            sorted_dates = sorted(po_series.keys(), reverse=True)
            total_open_orders = int(round(po_series[sorted_dates[0]]))

        # Do not fabricate status breakdowns, pending_approval, or monetary values
        open_orders_kpi = OpenPurchaseOrdersKpi(
            total_open_orders=total_open_orders,
            total_value_usd=None,
            pending_approval=None,
            by_status=None,
        )

        # --- 4. Logistics On-Time Delivery ---
        target_delivery_rate = 95.0
        delivery_current_rate = 0.0
        delivery_trend: str = "stable"
        delivery_change_pct: float | None = None
        total_shipments: int | None = None
        delivered_on_time: int | None = None
        delayed_shipments: int | None = None

        # Check historical on_time_delivery_pct from kpi_metrics for rate and trend
        deliv_series = self._extract_metric_series(kpi_rows, "on_time_delivery_pct", warehouse_id, category)
        if deliv_series:
            sorted_dates = sorted(deliv_series.keys(), reverse=True)
            raw_del = deliv_series[sorted_dates[0]]
            if 0.0 < raw_del <= 1.0:
                raw_del = raw_del * 100.0
            delivery_current_rate = min(100.0, max(0.0, round(raw_del, 2)))

            if len(sorted_dates) > 1:
                prev_raw = deliv_series[sorted_dates[1]]
                if 0.0 < prev_raw <= 1.0:
                    prev_raw = prev_raw * 100.0
                prev_del = min(100.0, max(0.0, round(prev_raw, 2)))
                d_diff = round(delivery_current_rate - prev_del, 2)
                delivery_change_pct = d_diff
                if d_diff > 0.05:
                    delivery_trend = "up"
                elif d_diff < -0.05:
                    delivery_trend = "down"

        # Prefer real shipment data from transport_performance when available
        if transport_data and transport_data.get("total_shipments", 0) > 0:
            total_shipments = transport_data["total_shipments"]
            delivered_on_time = transport_data["delivered_on_time"]
            delayed_shipments = transport_data["delayed"]
            if transport_data.get("known_shipments", 0) > 0:
                delivery_current_rate = min(100.0, max(0.0, transport_data["current_rate"]))

        if delivery_current_rate >= target_delivery_rate:
            delivery_status = "on_target"
        elif delivery_current_rate >= (target_delivery_rate - 5.0):
            delivery_status = "warning"
        else:
            delivery_status = "critical"

        delivery_kpi = OnTimeDeliveryKpi(
            current_rate=delivery_current_rate,
            target_rate=target_delivery_rate,
            total_shipments=total_shipments,
            delivered_on_time=delivered_on_time,
            delayed=delayed_shipments,
            status=delivery_status,  # type: ignore[arg-type]
            trend=delivery_trend,  # type: ignore[arg-type]
            change_percentage=delivery_change_pct,
        )

        filters_applied = FiltersApplied(
            warehouse_id=warehouse_id,
            category=category,
            start_date=start_date,
            end_date=end_date,
            window_days=window_days,
        )

        return KpiDashboardResponse(
            contract_version="v1",
            generated_at=datetime.now(timezone.utc).isoformat(),
            cached=False,
            cache_ttl_seconds=settings.LIVE_KPIS_CACHE_TTL_SECONDS,
            filters_applied=filters_applied,
            kpis=KpisPayload(
                fill_rate=fill_kpi,
                stockouts=stockouts_kpi,
                open_purchase_orders=open_orders_kpi,
                on_time_delivery=delivery_kpi,
            ),
        )

    async def get_kpis(
        self,
        warehouse_id: str | None = None,
        category: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        window_days: int = 30,
    ) -> dict[str, Any]:
        """
        Main entry point for retrieving KPIs.
        Checks Redis cache first; on cache miss, queries ClickHouse and caches the result.
        """
        cache_key = self._resolve_cache_key(
            warehouse_id=warehouse_id,
            category=category,
            start_date=start_date,
            end_date=end_date,
            window_days=window_days,
        )

        # 1. Attempt cache lookup
        cached_response = await self._get_from_cache(cache_key)
        if cached_response is not None:
            return cached_response

        # 2. Cache miss -> Query ClickHouse asynchronously in worker thread
        try:
            db_results = await asyncio.to_thread(
                self._query_clickhouse_sync,
                warehouse_id,
                category,
                start_date,
                end_date,
                window_days,
            )
        except Exception as exc:
            logger.error("ClickHouse connection or query failure: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="ClickHouse analytics data source unavailable",
            ) from exc

        # 3. Construct and validate response schema
        response_model = self._build_kpi_response(
            db_results=db_results,
            warehouse_id=warehouse_id,
            category=category,
            start_date=start_date,
            end_date=end_date,
            window_days=window_days,
        )
        response_dict = response_model.model_dump()

        # 4. Save to Redis cache
        await self._save_to_cache(
            cache_key=cache_key,
            response_dict=response_dict,
            ttl_seconds=settings.LIVE_KPIS_CACHE_TTL_SECONDS,
        )

        return response_dict


# Singleton service instance
analytics_kpi_service = AnalyticsKpiService()
