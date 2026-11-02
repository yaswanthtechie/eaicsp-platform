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


class KpiUnavailableError(Exception):
    """ClickHouse could not be queried; the route returns 503 SERVICE_UNAVAILABLE."""


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
        self, warehouse_id, category, start_date, end_date, window_days
    ) -> dict[str, Any]:
        client = self.get_clickhouse_client()
        try:
            return self._run_queries(
                client, warehouse_id, category, start_date, end_date, window_days
            )
        finally:
            client.close()

    @staticmethod
    def _rows(result: Any) -> list[Any]:
        return result.result_rows if hasattr(result, "result_rows") else (result or [])

    @staticmethod
    def _rate_and_trend(series: dict[str, float]) -> tuple[float | None, str, float | None]:
        """Latest rate, trend and change vs the previous day; kpi_metrics rates are already 0-100."""
        if not series:
            return None, "stable", None
        dates = sorted(series, reverse=True)
        current = min(100.0, max(0.0, round(series[dates[0]], 2)))
        if len(dates) == 1:
            return current, "stable", None
        previous = min(100.0, max(0.0, round(series[dates[1]], 2)))
        change = round(current - previous, 2)
        trend = "up" if change > 0.05 else "down" if change < -0.05 else "stable"
        return current, trend, change

    @staticmethod
    def _rate_status(rate: float | None, target: float) -> str:
        if rate is None:
            return "no_data"
        if rate >= target:
            return "on_target"
        if rate >= target - 5.0:
            return "warning"
        return "critical"

    def _run_queries(
        self,
        client: Any,
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
            kpi_rows = self._rows(result)
        except Exception as exc:
            logger.error("ClickHouse query error on kpi_metrics: %s", exc)
            raise

        # 2. Counts come from Vivek's KPI views (current state, not windowed).
        wh_params = {"warehouse_id": wh_filter}
        stockout_rows = self._rows(client.query(
            """
            SELECT warehouse_id, stockout_count, total_skus
            FROM kpi_stockouts_by_warehouse
            WHERE (%(warehouse_id)s = '' OR warehouse_id = %(warehouse_id)s)
            ORDER BY warehouse_id
            """,
            parameters=wh_params,
        ))
        fill_rows = self._rows(client.query(
            """
            SELECT sum(total_lines_ordered), sum(lines_fulfilled)
            FROM kpi_fill_rate_by_warehouse
            WHERE (%(warehouse_id)s = '' OR warehouse_id = %(warehouse_id)s)
            """,
            parameters=wh_params,
        ))
        po_rows = self._rows(client.query(
            """
            SELECT status, sum(open_po_count)
            FROM kpi_open_pos_by_status
            WHERE (%(warehouse_id)s = '' OR warehouse_id = %(warehouse_id)s)
            GROUP BY status
            """,
            parameters=wh_params,
        ))
        otd_rows = self._rows(client.query(
            """
            SELECT sum(total_shipments), sum(delivered_on_time), sum(delayed)
            FROM kpi_on_time_delivery_by_warehouse
            WHERE (%(warehouse_id)s = '' OR warehouse_id = %(warehouse_id)s)
            """,
            parameters=wh_params,
        ))
        return {
            "kpi_rows": kpi_rows,
            "stockout_rows": stockout_rows,
            "fill_counts": fill_rows[0] if fill_rows else (0, 0),
            "po_by_status": {str(status): int(count) for status, count in po_rows},
            "otd_counts": otd_rows[0] if otd_rows else (0, 0, 0),
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
        kpi_rows = db_results["kpi_rows"]

        # --- 1. Fill Rate ---
        target_fill_rate = 95.0
        fill_current_rate, fill_trend, fill_change_pct = self._rate_and_trend(
            self._extract_metric_series(kpi_rows, "fill_rate", warehouse_id, category)
        )
        lines_ordered, lines_fulfilled = (int(v or 0) for v in db_results["fill_counts"])
        fill_kpi = FillRateKpi(
            current_rate=fill_current_rate,
            target_rate=target_fill_rate,
            total_lines_ordered=lines_ordered,
            lines_fulfilled=lines_fulfilled,
            status=self._rate_status(fill_current_rate, target_fill_rate),
            trend=fill_trend,
            change_percentage=fill_change_pct,
        )

        # --- 2. Inventory Stockouts ---
        # Totals come from the view (current state); kpi_metrics only drives the trend.
        by_warehouse_list = [
            WarehouseStockout(
                warehouse_id=str(wh_id),
                stockout_count=int(stockouts),
                at_risk_count=None,
                total_skus=int(total_skus),
            )
            for wh_id, stockouts, total_skus in db_results["stockout_rows"]
            if CANONICAL_WAREHOUSE_RE.match(str(wh_id))
        ]
        total_stockouts = sum(w.stockout_count for w in by_warehouse_list)

        stockout_trend: str = "stable"
        stockout_series = self._extract_metric_series(
            kpi_rows, "stockout_count", warehouse_id, category
        )
        if len(stockout_series) > 1:
            latest, previous = (
                stockout_series[d]
                for d in sorted(stockout_series, reverse=True)[:2]
            )
            if latest < previous:
                stockout_trend = "improving"
            elif latest > previous:
                stockout_trend = "worsening"

        if total_stockouts == 0:
            stockouts_status = "normal"
        elif total_stockouts <= 20:
            stockouts_status = "warning"
        else:
            stockouts_status = "critical"

        stockouts_kpi = StockoutsKpi(
            total_stockouts=total_stockouts,
            critical_skus=None,
            at_risk_skus=None,
            status=stockouts_status,  # type: ignore[arg-type]
            trend=stockout_trend,  # type: ignore[arg-type]
            by_warehouse=by_warehouse_list,
        )

        # --- 3. Open Purchase Orders ---
        po_by_status = db_results["po_by_status"]
        approved = po_by_status.get("approved", 0)
        acknowledged = po_by_status.get("acknowledged", 0)
        in_transit = po_by_status.get("in_transit", 0)

        open_orders_kpi = OpenPurchaseOrdersKpi(
            total_open_orders=approved + acknowledged + in_transit,
            total_value_usd=None,
            pending_approval=None,
            by_status=POByStatus(
                draft=None,
                approved=approved,
                acknowledged=acknowledged,
                in_transit=in_transit,
            ),
        )

        # --- 4. Logistics On-Time Delivery ---
        target_delivery_rate = 95.0
        delivery_current_rate, delivery_trend, delivery_change_pct = self._rate_and_trend(
            self._extract_metric_series(kpi_rows, "on_time_delivery_pct", warehouse_id, category)
        )
        total_shipments, delivered_on_time, delayed_shipments = (
            int(v or 0) for v in db_results["otd_counts"]
        )
        delivery_kpi = OnTimeDeliveryKpi(
            current_rate=delivery_current_rate,
            target_rate=target_delivery_rate,
            total_shipments=total_shipments,
            delivered_on_time=delivered_on_time,
            delayed=delayed_shipments,
            status=self._rate_status(delivery_current_rate, target_delivery_rate),
            trend=delivery_trend,
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
            cache_ttl_seconds=None,
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
        force_refresh: bool = False,
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

        if not force_refresh:
            cached_response = await self._get_from_cache(cache_key)
            if cached_response is not None:
                return cached_response

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
            raise KpiUnavailableError() from exc

        response_model = self._build_kpi_response(
            db_results=db_results,
            warehouse_id=warehouse_id,
            category=category,
            start_date=start_date,
            end_date=end_date,
            window_days=window_days,
        )
        response_dict = response_model.model_dump()

        await self._save_to_cache(
            cache_key=cache_key,
            response_dict=response_dict,
            ttl_seconds=settings.LIVE_KPIS_CACHE_TTL_SECONDS,
        )

        return response_dict


# Singleton service instance
analytics_kpi_service = AnalyticsKpiService()
