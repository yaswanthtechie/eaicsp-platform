from alert_service import write_alert


def airflow_failure_callback(context):

    task_instance = context["task_instance"]

    write_alert(
        pipeline=context["dag"].dag_id,
        severity="CRITICAL",
        message=f"Task '{task_instance.task_id}' failed",
        run_id=context["run_id"]
    )