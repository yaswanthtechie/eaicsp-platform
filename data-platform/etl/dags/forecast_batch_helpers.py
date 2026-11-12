"""Pure helpers for nightly forecast batch. No Airflow or Docker dependency."""

import json
import math
import re
import uuid
from datetime import date, datetime, timezone


SKU_PATTERN = re.compile(r"SKU-\d{6}")
WAREHOUSE_PATTERN = re.compile(r"WH-[A-Z]{3}-\d{2}")


def validate_pair(sku, warehouse):
    """Validate canonical SKU and warehouse identifiers."""
    if not isinstance(sku, str) or not SKU_PATTERN.fullmatch(sku):
        raise ValueError(f"Invalid sku_id: {sku!r}")

    if not isinstance(warehouse, str) or not WAREHOUSE_PATTERN.fullmatch(warehouse):
        raise ValueError(f"Invalid warehouse_id: {warehouse!r}")


def build_rows(
    batch_date,
    forecasts_by_pair,
    model_version,
    generated_at,
    version,
    horizon,
    interval_level=0.8,
):
    """Validate forecasts and build ClickHouse rows."""
    if isinstance(batch_date, str):
        batch_date = date.fromisoformat(batch_date)

    rows = []

    for sku, warehouse, forecast in forecasts_by_pair:
        validate_pair(sku, warehouse)

        if len(forecast) != horizon:
            raise ValueError(
                f"{sku}/{warehouse}: expected {horizon} forecast points, "
                f"received {len(forecast)}"
            )

        for point in forecast:
            forecast_date = datetime.fromisoformat(
                str(point["date"]).replace("Z", "+00:00")
            ).date()

            predicted = float(point["predicted"])
            lower = float(point["lower_bound"])
            upper = float(point["upper_bound"])

            if not all(
                math.isfinite(value) and value >= 0
                for value in (predicted, lower, upper)
            ):
                raise ValueError(
                    f"Invalid forecast values for {sku}/{warehouse}"
                )

            if lower > predicted or predicted > upper:
                raise ValueError(
                    f"Invalid forecast interval for {sku}/{warehouse}"
                )

            rows.append(
                (
                    batch_date,
                    forecast_date,
                    sku,
                    warehouse,
                    predicted,
                    lower,
                    upper,
                    interval_level,
                    model_version,
                    generated_at,
                    version,
                )
            )

    return rows


def build_event(
    run_id,
    model_version,
    pairs,
    horizon,
    completed_at=None,
    duration_seconds=0.0,
    status="SUCCESS",
    message=None,
):
    """Build the forecast.batch.completed event using UUID v4."""
    if status not in {"SUCCESS", "PARTIAL"}:
        raise ValueError("status must be SUCCESS or PARTIAL")

    completed_at = completed_at or datetime.now(timezone.utc)

    if completed_at.tzinfo is None:
        completed_at = completed_at.replace(tzinfo=timezone.utc)

    completed_at = completed_at.astimezone(timezone.utc)
    pair_set = set(pairs)

    if message is None:
        message = f"Forecasted {len(pair_set)} SKU/warehouse pairs."

    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "forecast.batch.completed",
        "event_version": 1,
        "occurred_at": completed_at.isoformat(),
        "producer": "demand-forecast-service",
        "payload": {
            "run_id": run_id,
            "model_version": model_version,
            "granularity": "daily",
            "sku_count": len({sku for sku, _ in pair_set}),
            "warehouse_count": len({warehouse for _, warehouse in pair_set}),
            "horizon": horizon,
            "completed_at": completed_at.isoformat(),
            "status": status,
            "duration_seconds": max(0.0, float(duration_seconds)),
            "destination_mart": "clickhouse.demand_forecast_history",
            "message": str(message)[:300],
        },
    }


def write_batch(ch, cache, rows, cache_entries, columns, ttl):
    """Write ClickHouse rows and Redis cache entries using a pipeline."""
    for offset in range(0, len(rows), 5000):
        ch.insert(
            "demand_forecast_history",
            rows[offset:offset + 5000],
            column_names=columns,
        )

    if cache_entries:
        pipeline = cache.pipeline()
        for cache_key, cache_value in cache_entries:
            pipeline.set(cache_key, json.dumps(cache_value), ex=ttl)
        pipeline.execute()
