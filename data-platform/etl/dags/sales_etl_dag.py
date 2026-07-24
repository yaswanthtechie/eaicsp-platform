from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


with DAG(
    dag_id="sales_etl_pipeline",
    start_date=datetime(2026, 7, 1),
    schedule="@daily",
    catchup=False,
) as dag:

    run_etl = BashOperator(
        task_id="run_etl_pipeline",
        bash_command="python3 /opt/airflow/etl/src/main.py"
    )