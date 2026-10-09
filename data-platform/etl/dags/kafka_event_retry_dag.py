"""Retries pending pipeline events from the PostgreSQL outbox."""
from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator


def retry_events():
    from etl.src.kafka_events import retry_pending_events
    return retry_pending_events(limit=100)


with DAG(
    dag_id="etl_event_outbox_retry",
    start_date=datetime(2026, 7, 1),
    schedule="*/5 * * * *",
    catchup=False,
    tags=["etl", "kafka", "outbox"],
    default_args={"owner": "airflow", "retries": 0},
) as dag:
    PythonOperator(task_id="retry_pending_events", python_callable=retry_events)
