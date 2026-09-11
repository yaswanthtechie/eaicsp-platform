from alert_service import write_alert


def airflow_failure_callback(context):

    task_instance = context["task_instance"]

    run_id = task_instance.xcom_pull(
        task_ids="start_run",
        key="run_id",
    )

    write_alert(
        pipeline=context["dag"].dag_id,
        severity="CRITICAL",
        message=f"Task '{task_instance.task_id}' failed",
        run_id=run_id
    )