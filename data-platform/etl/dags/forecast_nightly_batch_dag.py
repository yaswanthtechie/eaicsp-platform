
"""Nightly production forecast batch: ClickHouse + Redis + Kafka."""

from __future__ import annotations

import csv
import json
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator


def run_forecast_batch(**context):
    import clickhouse_connect
    import redis
    from kafka import KafkaProducer
    from src.production_model import ProductionForecastModel

    started = time.monotonic()
    logical_date = context["logical_date"].in_timezone("UTC")
    batch_date = logical_date.date()
    batch_date_text = batch_date.isoformat()
    run_id = f"BATCH-{batch_date:%Y%m%d}-01"

    seed_path = Path(os.environ["SEED_SALES_PATH"])
    if not seed_path.is_file():
        raise FileNotFoundError(f"Seed sales file not found: {seed_path}")

    pairs = set()
    with seed_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"sku_id", "warehouse_id"}

        if not required.issubset(reader.fieldnames or []):
            raise ValueError(
                "Seed CSV must contain sku_id and warehouse_id columns."
            )

        for row in reader:
            sku = row["sku_id"].strip()
            warehouse = row["warehouse_id"].strip()

            if not sku or not warehouse:
                raise ValueError(
                    "Seed CSV contains an empty SKU or warehouse ID."
                )

            pairs.add((sku, warehouse))

    if not pairs:
        raise ValueError("No canonical SKU/warehouse pairs found in seed data.")

    horizon = int(os.getenv("FORECAST_HORIZON_DAYS", "30"))
    if not 1 <= horizon <= 90:
        raise ValueError("FORECAST_HORIZON_DAYS must be between 1 and 90.")

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
        # Idempotency: remove previous rows for this batch date
        # and wait until the ClickHouse mutation is completed.
        ch.command(
            """
            ALTER TABLE demand_forecast_history
            DELETE WHERE batch_date = {batch_date:Date}
            SETTINGS mutations_sync = 1
            """,
            parameters={"batch_date": batch_date},
        )

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

        rows = []
        ttl = int(os.getenv("FORECAST_CACHE_TTL_SECONDS", "86400"))

        for sku, warehouse in sorted(pairs):
            forecast = model.predict(sku, warehouse, horizon)

            if len(forecast) != horizon:
                raise ValueError(
                    f"{sku}/{warehouse}: expected {horizon} forecast points, "
                    f"received {len(forecast)}"
                )

            pair_rows = []

            for point in forecast:
                forecast_date = datetime.fromisoformat(
                    str(point["date"]).replace("Z", "+00:00")
                ).date()

                predicted = float(point["predicted"])
                lower = float(point["lower_bound"])
                upper = float(point["upper_bound"])

                if not all(
                    map(
                        lambda x: x >= 0 and x < float("inf"),
                        (predicted, lower, upper),
                    )
                ):
                    raise ValueError(
                        f"Invalid forecast values for {sku}/{warehouse}"
                    )

                if lower > predicted or predicted > upper:
                    raise ValueError(
                        f"Invalid forecast interval for {sku}/{warehouse}"
                    )

                pair_rows.append(
                    (
                        batch_date,
                        forecast_date,
                        sku,
                        warehouse,
                        predicted,
                        lower,
                        upper,
                        0.8,
                        model_version,
                        generated_at,
                        version,
                    )
                )

            rows.extend(pair_rows)

            # Redis uses deterministic keys, so reruns overwrite old values.
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
                "interval_level": 0.8,
                "generated_at": generated_at.isoformat(),
                "forecast": forecast,
            }

            cache.set(cache_key, json.dumps(cache_value), ex=ttl)

            if len(rows) >= 5000:
                ch.insert(
                    "demand_forecast_history",
                    rows,
                    column_names=columns,
                )
                rows.clear()

        if rows:
            ch.insert(
                "demand_forecast_history",
                rows,
                column_names=columns,
            )

        completed_at = datetime.now(timezone.utc)

        event = {
            # Deterministic event ID: same batch always gets the same ID.
            "event_id": str(uuid.uuid5(uuid.NAMESPACE_URL, run_id)),
            "event_type": "forecast.batch.completed",
            "event_version": 1,
            "occurred_at": completed_at.isoformat(),
            "producer": "demand-forecast-service",
            "payload": {
                "run_id": run_id,
                "model_version": model_version,
                "granularity": "daily",
                "sku_count": len({sku for sku, _ in pairs}),
                "warehouse_count": len(
                    {warehouse for _, warehouse in pairs}
                ),
                "horizon": horizon,
                "completed_at": completed_at.isoformat(),
                "status": "SUCCESS",
                "duration_seconds": round(
                    time.monotonic() - started, 3
                ),
                "destination_mart": "clickhouse.demand_forecast_history",
                "message": f"Forecasted {len(pairs)} SKU/warehouse pairs.",
            },
        }

        producer.send(
            "forecast.batch.completed",
            key=run_id.encode("utf-8"),
            value=json.dumps(event).encode("utf-8"),
        ).get(timeout=60)

        producer.flush(timeout=60)

        print(
            f"Batch {run_id} completed: {len(pairs)} pairs, "
            f"{horizon} daily periods, model {model_version}"
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
