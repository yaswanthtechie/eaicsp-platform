from alert_service import write_alert


def airflow_failure_callback(context):

    task_instance = context["task_instance"]

    etl_run_id = task_instance.xcom_pull(
        task_ids="extract",
        key="run_id",
    )

    write_alert(
        pipeline=context["dag"].dag_id,
        severity="CRITICAL",
        message=(
            f"Task '{task_instance.task_id}' failed "
            f"(airflow_run_id={context['run_id']})"
        ),
        run_id=etl_run_id,
    )
