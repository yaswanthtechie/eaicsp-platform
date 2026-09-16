"""
R4 Sales + Inventory ETL DAG

Important:
- Keep DAG parsing lightweight.
- Do not import pandas, database engines, or heavy ETL modules at DAG parse time.
- Pipeline configuration is read directly from pipeline_config.yaml using
  lightweight YAML parsing.
- Heavy ETL imports happen only when tasks execute.
"""

from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator

from etl.src.config_loader import load_pipeline_config
from etl.src.logging_config import logger


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# config_loader.py is the single source of truth for pipeline_config.yaml -
# it's what validate_schema_against() and the quality gate expect (a plain
# dict for `columns`, not a SimpleNamespace), and it's still cheap enough
# (just yaml.safe_load + dataclass construction) to run at DAG-parse time
# without pulling in pandas or a DB engine.

PIPELINE_CONFIG = load_pipeline_config()


# ---------------------------------------------------------------------------
# Validate source dependency ordering
# ---------------------------------------------------------------------------

_seen_sources = set()

for _source in PIPELINE_CONFIG.sources:

    if (
        _source.depends_on
        and _source.depends_on not in _seen_sources
    ):
        raise ValueError(
            f"pipeline_config.yaml: source '{_source.name}' depends on "
            f"'{_source.depends_on}', but that source must appear earlier "
            f"in the sources list."
        )

    _seen_sources.add(_source.name)


# ---------------------------------------------------------------------------
# Airflow failure callback
# ---------------------------------------------------------------------------

def airflow_failure_callback(context):
    """
    Import alert functionality only when a task actually fails.
    """

    from etl.src.alerts import airflow_failure_callback as _callback

    _callback(context)


# ---------------------------------------------------------------------------
# Default Airflow arguments
# ---------------------------------------------------------------------------

default_args = {
    "owner": "airflow",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": airflow_failure_callback,
}


# ---------------------------------------------------------------------------
# XCom serialization helpers
# ---------------------------------------------------------------------------

def _serialize_batches(batches):

    return [
        {
            "file_path": str(batch["file_path"]),
            "data": batch["data"].to_dict(orient="records"),
            "report": batch.get("report"),
        }
        for batch in batches
    ]


def _deserialize_batches(serialized):

    import pandas as pd

    result = []

    for item in serialized or []:

        batch = {
            "file_path": Path(item["file_path"]),
            "data": pd.DataFrame(item["data"]),
        }

        if item.get("report") is not None:
            batch["report"] = item["report"]

        result.append(batch)

    return result


# ---------------------------------------------------------------------------
# Start run
# ---------------------------------------------------------------------------

def start_run_task(**context):

    from etl.src.logger import create_run

    run_id = create_run()

    context["ti"].xcom_push(
        key="run_id",
        value=run_id,
    )

    logger.info(
        f"Pipeline run started: run_id={run_id}"
    )


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------

def make_extract_task(source_config, extract_task_id):

    def _extract(source_config=source_config, **context):

        from etl.src.alert_service import write_alert
        from etl.src.data_contract import validate_schema_against
        from etl.src.extract import extract_data
        from etl.src.watermark import get_watermark

        ti = context["ti"]

        run_id = ti.xcom_pull(
            task_ids="start_run",
            key="run_id",
        )

        watermark_name = (
            f"sales_etl_{source_config.name}"
        )

        last_processed_date = get_watermark(
            pipeline_name=watermark_name
        )

        extracted_batches = extract_data(
            last_processed_date=last_processed_date,
            source_path=source_config.path,
            date_column=source_config.date_column,
        )

        ti.xcom_push(
            key="batches_seen",
            value=len(extracted_batches),
        )

        if not extracted_batches:

            logger.warning(
                f"[{source_config.name}] No new files found"
            )

            return []

        ti.xcom_push(
            key="raw_batches",
            value=_serialize_batches(extracted_batches),
        )

        schema_valid = []

        for batch in extracted_batches:

            try:

                validate_schema_against(
                    batch["data"],
                    source_config.columns,
                )

                schema_valid.append(batch)

            except Exception as e:

                logger.error(
                    f"[{source_config.name}] "
                    f"Schema validation failed: {e}"
                )

                write_alert(
                    pipeline="sales_etl",
                    severity="WARN",
                    message=str(e),
                    batch_file=batch["file_path"].name,
                    run_id=run_id,
                )

        return _serialize_batches(schema_valid)

    return _extract


# ---------------------------------------------------------------------------
# Quality gate
# ---------------------------------------------------------------------------

def make_quality_gate_task(
    source_config,
    extract_task_id,
    load_task_id,
    reject_task_id,
):

    def _quality_gate(
        source_config=source_config,
        **context,
    ):

        from etl.src.quality_gate import quality_gate_generic

        ti = context["ti"]

        schema_valid_batches = _deserialize_batches(
            ti.xcom_pull(
                task_ids=extract_task_id
            )
        )

        if not schema_valid_batches:

            logger.warning(
                f"[{source_config.name}] "
                "All batches failed schema validation"
            )

            ti.xcom_push(
                key="rows_rejected_pre_load",
                value=0,
            )

            return reject_task_id

        validated_batches = quality_gate_generic(
            schema_valid_batches,
            source_config,
        )

        rejected_by_quality = (
            len(schema_valid_batches)
            - len(validated_batches)
        )

        ti.xcom_push(
            key="rows_rejected_pre_load",
            value=rejected_by_quality,
        )

        if not validated_batches:

            logger.warning(
                f"[{source_config.name}] "
                "All batches rejected by quality gate"
            )

            return reject_task_id

        ti.xcom_push(
            key="validated_batches",
            value=_serialize_batches(
                validated_batches
            ),
        )

        return load_task_id

    return _quality_gate


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def make_load_task(
    source_config,
    extract_task_id,
    quality_gate_task_id,
):

    def _load(
        source_config=source_config,
        **context,
    ):

        from etl.src.load import load_data_bulk_generic
        from etl.src.reconciliation import reconcile_load
        from etl.src.transform import transform_data_generic

        ti = context["ti"]

        run_id = ti.xcom_pull(
            task_ids="start_run",
            key="run_id",
        )

        validated_batches = _deserialize_batches(
            ti.xcom_pull(
                task_ids=quality_gate_task_id,
                key="validated_batches",
            )
        )

        raw_batches = _deserialize_batches(
            ti.xcom_pull(
                task_ids=extract_task_id,
                key="raw_batches",
            )
        )

        if not validated_batches:

            ti.xcom_push(
                key="rows_inserted",
                value=0,
            )

            ti.xcom_push(
                key="rows_updated",
                value=0,
            )

            ti.xcom_push(
                key="rows_rejected",
                value=0,
            )

            ti.xcom_push(
                key="status",
                value="SUCCESS",
            )

            return

        approved_batches = [
            dict(batch, data=batch["data"].copy())
            for batch in validated_batches
        ]

        data_frames = [
            batch["data"]
            for batch in validated_batches
        ]

        transformed = transform_data_generic(
            data_frames,
            source_config,
        )

        for batch, dataframe in zip(
            validated_batches,
            transformed,
        ):
            batch["data"] = dataframe

        transformed_batches = [
            dict(batch, data=batch["data"].copy())
            for batch in validated_batches
        ]

        rows_inserted, rows_updated = (
            load_data_bulk_generic(
                validated_batches,
                run_id,
                source_config,
            )
        )

        # R5 #4: automated reconciliation. Compares what the quality gate
        # approved for load against what's actually in the table for this
        # run_id - catches a silent partial load failure that schema/quality
        # validation (which never looks at the database) structurally can't.
        reconcile_load(
            raw_batches,
            approved_batches,
            transformed_batches,
            source_config,
            run_id,
        )

        rows_dropped_in_gate = sum(
            batch.get(
                "report",
                {},
            ).get(
                "rows_dropped",
                0,
            )
            for batch in validated_batches
        )

        rejected_pre_load = ti.xcom_pull(
            task_ids=quality_gate_task_id,
            key="rows_rejected_pre_load",
        ) or 0

        rows_rejected = (
            rejected_pre_load
            + rows_dropped_in_gate
        )

        non_empty_dates = []

        for batch in validated_batches:

            if not batch["data"].empty:

                latest_value = batch["data"][
                    source_config.date_column
                ].max()

                if hasattr(latest_value, "date"):
                    latest_value = latest_value.date()

                non_empty_dates.append(
                    latest_value
                )

        latest_date = (
            max(non_empty_dates)
            if non_empty_dates
            else None
        )

        ti.xcom_push(
            key="rows_inserted",
            value=rows_inserted,
        )

        ti.xcom_push(
            key="rows_updated",
            value=rows_updated,
        )

        ti.xcom_push(
            key="rows_rejected",
            value=rows_rejected,
        )

        ti.xcom_push(
            key="latest_date",
            value=(
                latest_date.isoformat()
                if latest_date
                else None
            ),
        )

        ti.xcom_push(
            key="status",
            value="SUCCESS",
        )

        logger.info(
            f"[{source_config.name}] "
            f"Loaded batches. "
            f"Inserted={rows_inserted} "
            f"Updated={rows_updated}"
        )

    return _load


# ---------------------------------------------------------------------------
# Reject
# ---------------------------------------------------------------------------

def make_reject_task(
    source_config,
    extract_task_id,
):

    def _reject(
        source_config=source_config,
        **context,
    ):

        from etl.src.alert_service import write_alert

        ti = context["ti"]

        run_id = ti.xcom_pull(
            task_ids="start_run",
            key="run_id",
        )

        batches_seen = ti.xcom_pull(
            task_ids=extract_task_id,
            key="batches_seen",
        ) or 0

        if batches_seen == 0:

            message = (
                f"No {source_config.name} "
                "batches to process"
            )

        else:

            message = (
                f"All {source_config.name} batches "
                "failed schema or quality validation"
            )

        logger.warning(message)

        write_alert(
            pipeline="sales_etl",
            severity="WARN",
            message=message,
            run_id=run_id,
        )

        ti.xcom_push(
            key="rows_rejected",
            value=batches_seen,
        )

        ti.xcom_push(
            key="status",
            value=(
                "SUCCESS"
                if batches_seen == 0
                else "REJECTED"
            ),
        )

    return _reject


# ---------------------------------------------------------------------------
# Watermark
# ---------------------------------------------------------------------------

def make_join_watermark_update(
    source_config,
    load_task_id,
):

    def _join(
        source_config=source_config,
        **context,
    ):

        from etl.src.watermark import update_watermark

        ti = context["ti"]

        latest_date = ti.xcom_pull(
            task_ids=load_task_id,
            key="latest_date",
        )

        if not latest_date:

            logger.info(
                f"[{source_config.name}] "
                "Skipping watermark update: "
                "no rows were loaded this run"
            )

            return

        update_watermark(
            datetime.fromisoformat(
                latest_date
            ).date(),
            pipeline_name=(
                f"sales_etl_{source_config.name}"
            ),
        )

        logger.info(
            f"[{source_config.name}] "
            f"Watermark advanced to {latest_date}"
        )

    return _join


# ---------------------------------------------------------------------------
# Run logging
# ---------------------------------------------------------------------------

def log_run_task(**context):

    from etl.src.logger import finish_run
    from etl.src.sla_monitor import check_run_duration_sla

    ti = context["ti"]

    run_id = ti.xcom_pull(
        task_ids="start_run",
        key="run_id",
    )

    total_batches = 0
    total_inserted = 0
    total_updated = 0
    total_rejected = 0

    statuses = []

    for source_config in PIPELINE_CONFIG.sources:

        extract_id = (
            f"extract_{source_config.name}"
        )

        load_id = (
            f"load_{source_config.name}"
        )

        reject_id = (
            f"reject_{source_config.name}"
        )

        total_batches += (
            ti.xcom_pull(
                task_ids=extract_id,
                key="batches_seen",
            ) or 0
        )

        total_inserted += (
            ti.xcom_pull(
                task_ids=load_id,
                key="rows_inserted",
            ) or 0
        )

        total_updated += (
            ti.xcom_pull(
                task_ids=load_id,
                key="rows_updated",
            ) or 0
        )

        rows_rejected = ti.xcom_pull(
            task_ids=load_id,
            key="rows_rejected",
        )

        if rows_rejected is None:

            rows_rejected = ti.xcom_pull(
                task_ids=reject_id,
                key="rows_rejected",
            ) or 0

        total_rejected += rows_rejected

        status = (
            ti.xcom_pull(
                task_ids=load_id,
                key="status",
            )
            or ti.xcom_pull(
                task_ids=reject_id,
                key="status",
            )
            or "FAILED"
        )

        statuses.append(status)

    overall_status = (
        "SUCCESS"
        if all(
            status == "SUCCESS"
            for status in statuses
        )
        else (
            "FAILED"
            if any(
                status == "FAILED"
                for status in statuses
            )
            else "REJECTED"
        )
    )

    finish_run(
        run_id=run_id,
        end_time=datetime.now(),
        status=overall_status,
        batches_seen=total_batches,
        rows_inserted=total_inserted,
        rows_updated=total_updated,
        rows_rejected=total_rejected,
    )

    logger.info(
        f"Pipeline run {run_id} finished "
        f"with status={overall_status}"
    )

    # R5 #2: SLA monitoring. A run that succeeds but takes far longer than
    # its own recent history hides a real problem just as much as an
    # outright failure - check regardless of overall_status.
    check_run_duration_sla(run_id)


# ---------------------------------------------------------------------------
# Archive
# ---------------------------------------------------------------------------

def archive_task(**context):

    from etl.src.archive import archive_old_sales

    ti = context["ti"]

    run_id = ti.xcom_pull(
        task_ids="start_run",
        key="run_id",
    )

    # archive_old_sales() takes the retention window in DAYS and derives the
    # cutoff date itself - passing a pre-computed date here raised a
    # TypeError on every run. Passing run_id through means a failed archive
    # now raises an alert tied to that specific run.
    result = archive_old_sales(
        cutoff_days=PIPELINE_CONFIG.archive.cutoff_days,
        run_id=run_id,
    )

    logger.info(
        f"Archive task result: {result}"
    )


# ---------------------------------------------------------------------------
# DAG
# ---------------------------------------------------------------------------

with DAG(
    dag_id="sales_etl_pipeline",
    description=(
        "Config-driven multi-source ETL "
        "pipeline with sales and inventory"
    ),
    default_args=default_args,
    start_date=datetime(2026, 7, 1),
    schedule=PIPELINE_CONFIG.schedule,
    catchup=False,
    tags=[
        "etl",
        "sales",
        "inventory",
        "r4",
    ],
) as dag:

    start_run = PythonOperator(
        task_id="start_run",
        python_callable=start_run_task,
    )

    for source_config in PIPELINE_CONFIG.sources:

        name = source_config.name

        extract_id = (
            f"extract_{name}"
        )

        quality_gate_id = (
            f"quality_gate_{name}"
        )

        load_id = (
            f"load_{name}"
        )

        reject_id = (
            f"reject_{name}"
        )

        join_id = (
            f"join_{name}"
        )

        extract = PythonOperator(
            task_id=extract_id,
            python_callable=make_extract_task(
                source_config,
                extract_id,
            ),
        )

        quality_gate = BranchPythonOperator(
            task_id=quality_gate_id,
            python_callable=make_quality_gate_task(
                source_config,
                extract_id,
                load_id,
                reject_id,
            ),
        )

        load = PythonOperator(
            task_id=load_id,
            python_callable=make_load_task(
                source_config,
                extract_id,
                quality_gate_id,
            ),
        )

        reject = PythonOperator(
            task_id=reject_id,
            python_callable=make_reject_task(
                source_config,
                extract_id,
            ),
        )

        join = PythonOperator(
            task_id=join_id,
            python_callable=make_join_watermark_update(
                source_config,
                load_id,
            ),
            trigger_rule="none_failed_min_one_success",
        )

        # Build the actual dependency graph from depends_on.
        # Every source also depends on start_run because extract tasks need
        # the run_id XCom created by start_run.
        start_run >> extract

        if source_config.depends_on:
            upstream_join = dag.get_task(
                f"join_{source_config.depends_on}"
            )
            upstream_join >> extract

        extract >> quality_gate
        quality_gate >> [load, reject]
        [load, reject] >> join

    log_run = PythonOperator(
        task_id="log_run",
        python_callable=log_run_task,
        trigger_rule="none_failed_min_one_success",
    )

    archive_old_data = PythonOperator(
        task_id="archive_old_data",
        python_callable=archive_task,
        trigger_rule="none_failed_min_one_success",
    )

    # log_run waits for every source to finish.
    for source_config in PIPELINE_CONFIG.sources:
        dag.get_task(
            f"join_{source_config.name}"
        ) >> log_run

    log_run >> archive_old_data
    