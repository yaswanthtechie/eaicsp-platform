# Sales ETL Pipeline

## Overview

I am implementing an end-to-end ETL (Extract, Transform, Load) pipeline for processing sales data.

The pipeline:

- Extracts sales CSV files.
- Validates data using schema and business rules.
- Transforms data into a standardized format.
- Loads data into PostgreSQL.
- Supports incremental loading using watermarks.
- Tracks every pipeline execution.
- Provides alerting.
- Is orchestrated using Apache Airflow.

## Technology Stack

- Python
- PostgreSQL
- SQLAlchemy
- Pandas
- Pandera
- Flask
- Apache Airflow
- Docker & Docker Compose

## Project Structure

    data-platform/
    │
    ├── dags/
    │   └── sales_etl_dag.py
    │
    ├── etl/
    │   └── src/
    │       ├── extract.py
    │       ├── transform.py
    │       ├── quality_gate.py
    │       ├── load.py
    │       ├── pipeline.py
    │       ├── main.py
    │       ├── alerts.py
    │       ├── alerts_api.py
    │       ├── lineage_api.py
    │       ├── alert_service.py
    │       ├── data_contract.py
    │       ├── pandera_schema.py
    │       └── schema_drift.py
    │
    ├── sql/
    │   └── schema.sql
    │
    └── docker-compose.yml

## ETL Pipeline Flow

The pipeline is orchestrated using Apache Airflow.

    CSV Files
        |
        v
      Extract
        |
        v
    Quality Gate
        |
        v
    BranchPythonOperator
        |
        +------------------+
        |                  |
        v                  v
       Load        Reject & Notify
        |
        v
    Update Watermark
        |
        v
    Log Pipeline Run

The quality gate determines whether the data proceeds to loading or is rejected and reported.

## Database Tables

The pipeline uses the following PostgreSQL tables:

| Table | Purpose |
|---|---|
| `sales_fact` | Stores processed sales records |
| `etl_watermark` | Tracks the last processed date for incremental loading |
| `etl_run_log` | Stores ETL execution history |
| `sales_fact_history` | Stores previous versions of updated records |
| `etl_alerts` | Stores pipeline alerts and failures |

The `sales_fact` table also stores:

- `run_id`
- `pipeline_version`

These fields associate loaded records with a pipeline execution and pipeline version.

## Database Setup

Before running the pipeline, initialize the PostgreSQL database using:

    sql/schema.sql

The schema creates the required tables:

- `sales_fact`
- `etl_watermark`
- `etl_run_log`
- `sales_fact_history`
- `etl_alerts`

These tables support:

- Incremental loading
- Pipeline execution logging
- Alerting
- Change history
- Pipeline run tracking

## Running the Project

Start the Docker services:

    docker compose up -d

Run the ETL pipeline directly:

    python etl/src/main.py

The pipeline can also be executed through Apache Airflow by triggering the `sales_etl_pipeline` DAG from the Airflow UI.

## Features

### Incremental Loading

The pipeline uses the watermark table to determine the last processed date and avoid unnecessary reprocessing.

### Data Quality

The pipeline validates:

- Required columns
- Data types
- Extra columns
- Missing columns
- Business validation rules
- Schema drift

Pandera validation is also wired into the pipeline schema-validation stage.

Invalid batches are rejected before loading.

### UPSERT Loading

The loader performs INSERT or UPDATE operations using PostgreSQL `ON CONFLICT`.

Each loaded record also stores:

- `run_id`
- `pipeline_version`

### Change History

Previous versions of records are stored in `sales_fact_history` when processing existing sales records.

### Run Logging

Each execution records:

- Start time
- Finish time
- Status
- Inserted rows
- Updated rows
- Rejected rows
- Error message, if any

### Alerts

Pipeline and stage failures are written into the `etl_alerts` table.

The alerts API supports filtering recent alerts using the `since` parameter.

Example:

    GET /alerts?since=1h

The API also supports minute-based filters such as:

    GET /alerts?since=10m

## Airflow

The pipeline is orchestrated using Apache Airflow.

Airflow provides:

- Scheduling
- Monitoring
- Logging
- Retry support
- DAG visualization
- Task-level execution
- Quality-based branching

The DAG follows this task flow:

    extract
       |
       v
    quality_gate
       |
       v
    BranchPythonOperator
       |------------------+
       |                  |
       v                  v
      load        reject_and_notify
       |
       v
    update_watermark
       |
       v
      log_run

## Backfill

Historical data can be processed using the backfill command:

    python etl/src/main.py backfill --from YYYY-MM-DD --to YYYY-MM-DD

Example:

    python etl/src/main.py backfill --from 2026-07-01 --to 2026-07-31

## Useful Database Commands

View processed sales records:

    SELECT *
    FROM sales_fact
    LIMIT 5;

View recent ETL runs:

    SELECT *
    FROM etl_run_log
    ORDER BY run_id DESC
    LIMIT 5;

View the current watermark:

    SELECT *
    FROM etl_watermark;

View sales history:

    SELECT *
    FROM sales_fact_history
    LIMIT 5;

View generated alerts:

    SELECT *
    FROM etl_alerts
    ORDER BY created_at DESC
    LIMIT 5;

## Testing

Run the test suite with:

    pytest -q

The schema validation tests cover:

- Missing required columns
- Incorrect data types
- Extra columns

## Pipeline Monitoring

The Airflow UI can be used to monitor individual pipeline stages, task status, retries, logs, and branching behavior.

The PostgreSQL ETL tables can be queried to verify:

- Pipeline execution status
- Rows inserted
- Rows updated
- Rows rejected
- Watermark progress
- Generated alerts
- Historical records
## Generating Sample Data

The pipeline reads CSV batches from `data/batches/`, which is gitignored. Generate sample batches with:

    python etl/src/make_batches.py

## Environment

Copy `.env.example` to `.env` and set `DB_PASSWORD`.

When the pipeline runs inside Docker/Airflow, use `DB_HOST=postgres`. When running `python etl/src/main.py` from the host, use `DB_HOST=localhost` because Docker publishes PostgreSQL on port 5432.

## What Works / What Doesn't

### Working

- Airflow DAG with quality-based branching and downstream trigger rules.
- Data contract validation and schema drift detection, including broken-file tests.
- Alerts table and `GET /alerts?since=` filtering.
- Idempotent upsert, watermarks, and incremental loads.
- Historical backfill with date ordering and progress/ETA logging.
- Row-level lineage through `/lineage/row/{id}`.

### Known Limitations

- Concurrent loads are serialized by a transaction-scoped PostgreSQL advisory lock.
- Alert webhooks are not implemented; alerts remain in `etl_alerts` and are available through the API.
- Airflow runs from the pinned Docker image (`apache/airflow:2.10.5`). The main `requirements.txt` contains the application/test dependencies; Airflow dependencies are kept separate for local DAG linting.
