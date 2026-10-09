from datetime import datetime
from airflow import DAG
from airflow.operators.bash import BashOperator

# Manually triggered only (schedule=None); not part of the daily sales_etl_pipeline.
# conf values go through env vars (not string-interpolated into the shell) and the
# script itself validates YYYY-MM.
with DAG(
    dag_id="sales_spark_historical_backfill",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    tags=["r14", "spark", "backfill"],
) as dag:
    BashOperator(
        task_id="spark_monthly_backfill",
        env={
            "SPARK_MASTER": "local[1]",
            "SPARK_SHUFFLE_PARTITIONS": "16",
            "BF_INPUT": "{{ dag_run.conf.get('input', '/opt/airflow/data/backfill/sales_history.csv') }}",
            "BF_START": "{{ dag_run.conf.get('start_month', '2024-01') }}",
            "BF_END": "{{ dag_run.conf.get('end_month', '2024-12') }}",
        },
        append_env=True,
        bash_command=(
            'python /opt/airflow/spark/sales_backfill.py '
            '--input "$BF_INPUT" --start-month "$BF_START" --end-month "$BF_END" --run-id 0'
        ),
    )
