from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "airflow",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="sales_etl_pipeline",
    description="Daily Sales ETL Pipeline",
    default_args=default_args,
    start_date=datetime(2026, 7, 1),
    schedule="@daily",
    catchup=False,
    tags=["etl", "sales"],
) as dag:

    run_etl = BashOperator(
        task_id="run_etl_pipeline",
        bash_command="python3 /opt/airflow/etl/src/main.py",
    )