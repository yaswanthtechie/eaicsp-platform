from datetime import datetime, timedelta
import sys

from airflow import DAG
from airflow.operators.python import (
    PythonOperator,
    BranchPythonOperator,
)

# Make the project package and src modules available.
sys.path.insert(0, "/opt/airflow")
sys.path.insert(0, "/opt/airflow/etl/src")

from etl.src.alerts import airflow_failure_callback
from etl.src.pipeline import (
    extract_airflow_task,
    quality_gate_airflow_task,
    load_airflow_task,
    reject_and_notify_airflow_task,
    update_watermark_airflow_task,
    log_run_airflow_task,
)


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

    extract = PythonOperator(
        task_id="extract",
        python_callable=extract_airflow_task,
    )

    quality_gate = BranchPythonOperator(
        task_id="quality_gate",
        python_callable=quality_gate_airflow_task,
    )

    load = PythonOperator(
        task_id="load",
        python_callable=load_airflow_task,
    )

    reject_and_notify = PythonOperator(
        task_id="reject_and_notify",
        python_callable=reject_and_notify_airflow_task,
    )

    update_watermark = PythonOperator(
        task_id="update_watermark",
        python_callable=update_watermark_airflow_task,
        trigger_rule="none_failed_min_one_success",
    )

    log_run = PythonOperator(
        task_id="log_run",
        python_callable=log_run_airflow_task,
        trigger_rule="none_failed_min_one_success",
    )

    extract >> quality_gate >> [
        load,
        reject_and_notify,
    ] >> update_watermark >> log_run