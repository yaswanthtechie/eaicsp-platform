from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from alerts import airflow_failure_callback

default_args = {
    "owner": "airflow",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": airflow_failure_callback,
}

with DAG(
    dag_id="sales_etl_pipeline",
    description="Daily Sales ETL Pipeline",
    default_args=default_args,
    start_date=datetime(2026, 7, 1),
    schedule="0 2 * * *",
    catchup=False,
    tags=["etl", "sales"],
) as dag:

    run_etl = BashOperator(
        task_id="run_etl_pipeline",
        bash_command="python3 /opt/airflow/etl/src/main.py",
    )