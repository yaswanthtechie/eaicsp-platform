FROM apache/airflow:2.10.5

USER root
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless \
 && rm -rf /var/lib/apt/lists/*

USER airflow

RUN python -m venv /home/airflow/dbt_venv \
 && /home/airflow/dbt_venv/bin/pip install --no-cache-dir "dbt-core==1.9.4" "dbt-postgres==1.9.0"

ENV DBT_BIN=/home/airflow/dbt_venv/bin/dbt

RUN pip install --no-cache-dir \
    "clickhouse-connect==0.8.18" \
    "kafka-python>=2.2.0,<3" \
    "pyspark==3.5.3" \
    "mlflow==3.15.1" \
    "redis==5.2.1" \
    "prophet==1.4.0" \
    "holidays==0.101"
