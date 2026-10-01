#!/usr/bin/env bash
# R12-13 end-to-end verification. Run from the etl/ folder with Docker running.
# Stops at the first failure. Read-only except for the containers it starts.
set -euo pipefail
step() { printf '\n=== %s ===\n' "$1"; }

step "1. Unit tests (no Docker needed)"
pytest -m "not integration" -q

step "2. Start stack and wait for healthy"
docker compose up -d --build
sleep 45
docker compose ps

step "3. DAG import errors (must be empty)"
docker compose exec -T airflow-scheduler airflow dags list-import-errors

step "4. dbt debug + build (models AND tests)"
docker compose exec -T airflow-scheduler bash -c \
  '$DBT_BIN debug --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt && \
   $DBT_BIN build --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt'

step "5. Integration tests (Kafka, ClickHouse, outbox)"
pytest -m integration -v

step "6. ClickHouse vs Postgres benchmark (writes docs/r12_13_clickhouse_benchmark.json)"
python scripts/benchmark_postgres_clickhouse.py --rows 1200000

step "7. Done. Now do the manual checks in the checklist (failed run, Kafka outage, re-run same range)."
