"""Manual client ingestion: load, build KPIs, then run quality checks."""
import uuid
from datetime import datetime

from airflow import DAG
from airflow.models.param import Param
from airflow.operators.python import PythonOperator


def load_client_files(folder_path, **context):
    from client_ingest.load_client_data import main as load_main

    dag_run_id = context["dag_run"].run_id
    run_id = str(uuid.uuid5(uuid.NAMESPACE_URL, dag_run_id))
    return load_main(folder_path, run_id)


def build_client_kpis(**context):
    from client_ingest.build_client_kpis import build_client_kpis as build
    from client_ingest.build_client_kpis import _client, _database
    from database import get_engine

    client = _client()
    try:
        return build(get_engine(), client, _database())
    finally:
        client.close()


def check_client_quality(folder_path, **context):
    from client_ingest.quality_checks import run_quality_checks
    from database import get_engine

    run_id = context["ti"].xcom_pull(task_ids="load_client_files")
    return run_quality_checks(folder_path, run_id, get_engine())


with DAG(
    dag_id="client_data_load",
    description="Manually load client files, build KPIs, and validate data quality",
    start_date=datetime(2025, 1, 1),
    schedule=None,
    catchup=False,
    params={
        "folder_path": Param(
            "/opt/airflow/client_ingest/samples/client_format",
            type="string",
            minLength=1,
        )
    },
    tags=["client-ingestion"],
) as dag:
    load_task = PythonOperator(
        task_id="load_client_files",
        python_callable=load_client_files,
        op_kwargs={"folder_path": "{{ params.folder_path }}"},
    )

    kpi_task = PythonOperator(
        task_id="build_client_kpis",
        python_callable=build_client_kpis,
    )

    quality_task = PythonOperator(
        task_id="check_client_quality",
        python_callable=check_client_quality,
        op_kwargs={"folder_path": "{{ params.folder_path }}"},
    )

    load_task >> quality_task >> kpi_task
