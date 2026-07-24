# Data Engineering ETL Pipeline

## Project Overview

This project implements an end-to-end ETL (Extract, Transform, Load) pipeline using Python, PostgreSQL, Docker, and Apache Airflow.

The pipeline extracts daily sales batch files, validates and transforms the data, loads it into PostgreSQL using an idempotent upsert strategy, tracks processed batches using a watermark, records pipeline execution history, and can be orchestrated through Apache Airflow.

---

## Tech Stack

- Python
- Pandas
- SQLAlchemy
- PostgreSQL
- Docker
- Apache Airflow

---

## Project Structure

```
data_platform/
│
├── dags/
│
├── etl/
│   ├── data/
│   │   ├── batches/
│   │   └── rejected/
│   │
│   ├── logs/
│   │
│   ├── sql/
│   │
│   └── src/
│
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Features

- Extract sales batch CSV files
- Data transformation using Pandas
- Data Quality Gate
- Idempotent Upsert using PostgreSQL
- Incremental Loading using Watermark
- Audit Logging
- Apache Airflow orchestration

---

## Database Tables

### sales_fact

Stores cleaned sales records.

### etl_watermark

Stores the latest successfully processed date.

### etl_run_log

Stores execution history including success and failure logs.

---

## How to Run

### 1. Start Docker

```bash
docker compose up -d
```

### 2. Run ETL Pipeline

```bash
python etl/src/main.py
```

### 3. Run Airflow

Open:

```
http://localhost:8080
```

Trigger the DAG from the Airflow UI.

---

## Idempotency

The pipeline uses PostgreSQL's `ON CONFLICT DO UPDATE` statement.

Running the pipeline multiple times does not create duplicate records because existing records are updated instead of inserted again.

---

## Incremental Loading

The pipeline uses a watermark table (`etl_watermark`) to store the latest processed date.

During each execution, only records newer than the watermark are extracted and loaded into the destination table.

This avoids reprocessing previously loaded data and improves performance.

---

## Quality Gate

The pipeline validates each batch before loading.

Validation rules:

- Null rate in `quantity_sold` must be less than 10%
- Negative quantity must be less than 5%
- Batch row count must be between 100 and 2000 rows

Invalid batches are rejected and moved to the `data/rejected` folder.

---

## Audit Logging

Every pipeline execution is recorded in the `etl_run_log` table.

The audit log stores:

- Pipeline name
- Start time
- End time
- Status
- Rows inserted
- Error message (if any)

---

## Airflow

The ETL pipeline can also be executed through Apache Airflow.

The DAG automates the pipeline execution and provides monitoring through the Airflow UI.

---

