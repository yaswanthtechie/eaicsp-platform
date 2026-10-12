FROM apache/airflow:2.10.5

# R14: PySpark (local mode) needs a JRE; the stock Airflow image has none.
USER root
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless \
 && rm -rf /var/lib/apt/lists/*

USER airflow

# dbt is installed in its OWN virtualenv. dbt-postgres cannot be resolved together
# with Airflow's pinned dependencies (protobuf etc.); a shared install would either
# fail or silently upgrade packages Airflow depends on.
RUN python -m venv /home/airflow/dbt_venv \
 && /home/airflow/dbt_venv/bin/pip install --no-cache-dir "dbt-core==1.9.4" "dbt-postgres==1.9.0"
ENV DBT_BIN=/home/airflow/dbt_venv/bin/dbt

# These two coexist with Airflow's constraints (checked with pip --dry-run).
# kafka-python 2.0.x does not import on Python 3.12 (the image's Python); 3.x renamed configs.
RUN pip install --no-cache-dir "clickhouse-connect==0.8.18" "kafka-python>=2.2.0,<3" "pyspark==3.5.3"
