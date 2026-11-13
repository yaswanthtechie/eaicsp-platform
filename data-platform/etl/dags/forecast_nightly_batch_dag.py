"""Nightly production forecast batch: ClickHouse + Redis + Kafka."""

from __future__ import annotations

import csv
import json
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator

from forecast_batch_helpers import build_event, build_rows, validate_pair, write_batch


def run_forecast_batch(**context):
    import clickhouse_connect
    import redis
    from kafka import KafkaProducer
    from src.production_model import ProductionForecastModel

    started = time.monotonic()

    # Use the end of the Airflow data interval as the batch date.
    logical_date = context["data_interval_end"].in_timezone("UTC")
    batch_date = logical_date.date()
    batch_date_text = batch_date.isoformat()
    run_id = f"BATCH-{batch_date:%Y%m%d}-01"

    seed_path = Path(os.environ["SEED_SALES_PATH"])
    if not seed_path.is_file():
        raise FileNotFoundError(f"Seed sales file not found: {seed_path}")

    pairs = set()
    invalid_pairs = []

    with seed_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"sku_id", "warehouse_id"}

        if not required.issubset(reader.fieldnames or []):
            raise ValueError(
                "Seed CSV must contain sku_id and warehouse_id columns."
            )

        for row in reader:
            sku = (row.get("sku_id") or "").strip()
            warehouse = (row.get("warehouse_id") or "").strip()

            try:
                validate_pair(sku, warehouse)
                pairs.add((sku, warehouse))
            except ValueError as exc:
                invalid_pairs.append(
                    (sku or "<empty>", warehouse or "<empty>", str(exc))
                )

    if not pairs and not invalid_pairs:
        raise ValueError("Seed CSV contains no SKU/warehouse rows.")

    horizon = int(os.getenv("FORECAST_HORIZON_DAYS", "30"))
    if not 1 <= horizon <= 90:
        raise ValueError("FORECAST_HORIZON_DAYS must be between 1 and 90.")

    interval_level = float(os.getenv("FORECAST_INTERVAL_LEVEL", "0.8"))
    if not 0 < interval_level < 1:
        raise ValueError("FORECAST_INTERVAL_LEVEL must be between 0 and 1.")

    model = ProductionForecastModel().load()
    model_version = (
        f"{os.environ['MLFLOW_MODEL_NAME']}/{model.model_version}"
    )

    generated_at = datetime.now(timezone.utc)
    version = generated_at

    ch = clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.environ["CLICKHOUSE_PASSWORD"],
        database=os.getenv("CLICKHOUSE_DATABASE", "analytics"),
        connect_timeout=10,
        send_receive_timeout=120,
    )

    cache = redis.Redis.from_url(
        os.environ["FORECAST_REDIS_URL"],
        decode_responses=True,
    )

    producer = KafkaProducer(
        bootstrap_servers=os.environ["KAFKA_BOOTSTRAP_SERVERS"].split(","),
        acks="all",
        retries=5,
        max_in_flight_requests_per_connection=1,
    )

    try:
        # Process each pair independently. A failed pair must not stop the batch.
        successful_pairs = set()
        failed_pairs = list(invalid_pairs)
        rows = []
        cache_entries = []

        ttl = int(os.getenv("FORECAST_CACHE_TTL_SECONDS", "86400"))

        for sku, warehouse in sorted(pairs):
            try:
                forecast = model.predict(sku, warehouse, horizon)

                # Validate this pair's forecast before adding any output.
                pair_rows = build_rows(
                    batch_date=batch_date,
                    forecasts_by_pair=[(sku, warehouse, forecast)],
                    model_version=model_version,
                    generated_at=generated_at,
                    version=version,
                    horizon=horizon,
                    interval_level=interval_level,
                )

                rows.extend(pair_rows)
                successful_pairs.add((sku, warehouse))

                cache_key = (
                    f"forecast_cache:{batch_date_text}:{sku}:{warehouse}"
                )

                cache_value = {
                    "run_id": run_id,
                    "batch_date": batch_date_text,
                    "sku_id": sku,
                    "warehouse_id": warehouse,
                    "model_version": model_version,
                    "granularity": "daily",
                    "horizon": horizon,
                    "interval_level": interval_level,
                    "generated_at": generated_at.isoformat(),
                    "forecast": forecast,
                }

                cache_entries.append((cache_key, cache_value))

            except Exception as exc:
                failed_pairs.append((sku, warehouse, str(exc)))
                print(
                    f"Forecast failed for {sku}/{warehouse}: "
                    f"{type(exc).__name__}: {exc}"
                )

        if not successful_pairs:
            print("No SKU/warehouse pairs produced a valid forecast.")

        status = "PARTIAL" if failed_pairs else "SUCCESS"
        message = (
            f"Forecasted {len(successful_pairs)} of {len(pairs)} pairs; "
            f"{len(failed_pairs)} failed."
        )

        if failed_pairs:
            failed_summary = "; ".join(
                f"{sku}/{warehouse}: {reason}"
                for sku, warehouse, reason in failed_pairs
            )
            message = f"{message} Failures: {failed_summary}"[:300]

        columns = [
            "batch_date",
            "forecast_date",
            "sku_id",
            "warehouse_id",
            "predicted",
            "lower_bound",
            "upper_bound",
            "interval_level",
            "model_version",
            "generated_at",
            "version",
        ]

        # ReplacingMergeTree(version) handles reruns.
        # Consumers should use SELECT ... FINAL for deduplicated results.
        write_batch(
            ch=ch,
            cache=cache,
            rows=rows,
            cache_entries=cache_entries,
            columns=columns,
            ttl=ttl,
        )

        completed_at = datetime.now(timezone.utc)

        event = build_event(
            run_id=run_id,
            model_version=model_version,
            pairs=successful_pairs,
            horizon=horizon,
            completed_at=completed_at,
            duration_seconds=round(time.monotonic() - started, 3),
            status=status,
            message=message,
        )

        producer.send(
            "forecast.batch.completed",
            key=run_id.encode("utf-8"),
            value=json.dumps(event).encode("utf-8"),
        ).get(timeout=60)

        producer.flush(timeout=60)

        print(
            f"Batch {run_id} completed: {len(pairs)} pairs, "
            f"{horizon} daily periods, {len(rows)} rows, "
            f"model {model_version}"
        )

    finally:
        producer.close()
        cache.close()
        ch.close()


with DAG(
    dag_id="forecast_nightly_batch",
    description=(
        "Generate Production forecasts and publish them "
        "to ClickHouse, Redis and Kafka."
    ),
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    schedule="0 1 * * *",
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "demand-forecast-service",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["forecast", "nightly", "r15"],
) as dag:
    PythonOperator(
        task_id="generate_and_publish_forecasts",
        python_callable=run_forecast_batch,
    )