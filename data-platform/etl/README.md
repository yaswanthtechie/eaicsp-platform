# Sales ETL Data Pipeline

## Project Overview

This project implements an end-to-end ETL (Extract, Transform, Load) data pipeline for daily sales data using Python, PostgreSQL, Docker, and Apache Airflow.

The pipeline extracts sales data from CSV files, validates data quality, transforms the data, and loads it into a PostgreSQL database while supporting incremental loading through a watermark mechanism. Airflow is used to schedule and automate the pipeline execution.

---

## Architecture

```
                CSV Files
                    │
                    ▼
              Extract Data
                    │
                    ▼
             Quality Gate
                    │
                    ▼
              Transform Data
                    │
                    ▼
             Load (UPSERT)
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
 Watermark Table         ETL Run Log
                    │
                    ▼
            PostgreSQL Database
                    │
                    ▼
              Apache Airflow
```

---

## Technologies Used

- Python
- PostgreSQL
- SQLAlchemy
- Apache Airflow
- Docker & Docker Compose
- Pandas

---

## Project Structure

```
data_platform/
│
├── dags/
│   └── sales_etl_pipeline.py
│
├── etl/
│   └── src/
│       ├── config.py
│       ├── database.py
│       ├── extract.py
│       ├── quality_gate.py
│       ├── transform.py
│       ├── load.py
│       ├── watermark.py
│       ├── logger.py
│       ├── logging_config.py
│       ├── pipeline.py
│       ├── make_batches.py
│       └── main.py
│
├── sql/
│   └── schema.sql
│
├── data/
│   ├── batches/
│   └── rejected/
│
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Database Tables

The project uses three main tables:

### sales_fact

Stores processed sales records.

### etl_watermark

Tracks the latest processed business date for incremental loading.

### etl_run_log

Stores ETL execution details including:

- Pipeline status
- Start time
- End time
- Rows inserted
- Rows rejected
- Error messages

---

## ETL Workflow

1. Extract CSV files from the batches folder.
2. Apply Quality Gate validations:
   - Reject batches with fewer than 100 rows or more than 2000 rows.
   - Reject batches with more than 10% null values.
   - Reject batches with more than 5% negative quantities.
3. Transform data:
   - Remove duplicate records.
   - Convert columns to the correct data types.
4. Load data into PostgreSQL using UPSERT.
5. Update the watermark table.
6. Log pipeline execution details.

---

## Setup Instructions

### Clone the project

```bash
git clone <repository-url>
cd data_platform
```

### Start Docker services

```bash
docker compose up -d
```

### Verify containers

```bash
docker ps
```

---

## Initialize Database

Connect to PostgreSQL and execute:

```bash
psql -U admin -d salesdb
```

Run:

```sql
\i sql/schema.sql
```

---

## Generate Sample Data

```bash
python etl/src/make_batches.py
```

---

## Run the ETL Pipeline

```bash
python etl/src/main.py
```

---

## Run Using Apache Airflow

1. Open Airflow UI:

```
http://localhost:8080
```

Default credentials:

```
Username: airflow
Password: airflow
```

2. Enable the DAG:

```
sales_etl_pipeline
```

3. Click **Trigger DAG** to execute the pipeline.

---

## Features

- Incremental loading using watermark
- UPSERT to prevent duplicate records
- Data quality validation
- Automatic rejection of invalid batches
- ETL execution logging
- Airflow scheduling
- Dockerized deployment

---


Data Engineering Project