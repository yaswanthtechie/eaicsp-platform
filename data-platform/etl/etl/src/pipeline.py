from datetime import datetime

from extract import extract_data
from transform import transform_data
from quality_gate import quality_gate
from load import load_data
from watermark import get_watermark, update_watermark
from logger import create_run, finish_run
from logging_config import logger
from data_contract import validate_schema
from schema_drift import detect_schema_drift
from alert_service import write_alert
from pandera_schema import validate_with_pandera


 

def validate_batches(extracted_batches, run_id=None):

    valid_batches = []

    for batch in extracted_batches:

        try:

            validate_schema(batch["data"])
            validate_with_pandera(batch["data"])
            drift = detect_schema_drift(batch["data"])

            if (
                drift["added_columns"]
                or drift["removed_columns"]
                or drift["datatype_changes"]
            ):
                logger.warning(f"Schema Drift Detected: {drift}")

            valid_batches.append(batch)

        except Exception as e:

            logger.error(f"Schema validation failed: {e}")

            write_alert(
                pipeline="sales_etl",
                severity="WARN",
                message=str(e),
                batch_file=batch["file_path"].name,
                run_id=run_id
            )

    return valid_batches


def run_pipeline():

    start_time = datetime.now()

    run_id = create_run()

    try:

        logger.info("Pipeline Started")

        last_processed_date = get_watermark()

        extracted_batches = extract_data(last_processed_date)

        if not extracted_batches:

            logger.warning("No new files found")

            end_time = datetime.now()

            finish_run(
                run_id=run_id,
                end_time=end_time,
                status="SUCCESS",
                batches_seen=0,
                rows_inserted=0,
                rows_updated=0,
                rows_rejected=0
            )

            return

        batches_seen = len(extracted_batches)

        extracted_batches = validate_batches(extracted_batches, run_id=run_id)

        if not extracted_batches:

            logger.warning("All batches failed schema validation")

            end_time = datetime.now()

            finish_run(
                run_id=run_id,
                end_time=end_time,
                status="FAILED",
                batches_seen=batches_seen,
                rows_inserted=0,
                rows_updated=0,
                rows_rejected=batches_seen,
                error_message="Schema validation failed"
            )

            return

        validated_batches = quality_gate(extracted_batches)

        rejected_batches = batches_seen - len(validated_batches)

        if not validated_batches:

            logger.warning("All batches rejected")

            end_time = datetime.now()

            finish_run(
                run_id=run_id,
                end_time=end_time,
                status="REJECTED",
                batches_seen=batches_seen,
                rows_inserted=0,
                rows_updated=0,
                rows_rejected=rejected_batches,
                error_message="All batches rejected"
            )

            return

        data_frames = [
            batch["data"]
            for batch in validated_batches
        ]

        transformed_data = transform_data(data_frames)

        for batch, df in zip(validated_batches, transformed_data):
            batch["data"] = df

        rows_inserted, rows_updated = load_data(
            validated_batches,
            run_id
        )

        rows_rejected = rejected_batches + sum(
            batch["report"]["rows_dropped"]
            for batch in validated_batches
        )

        latest_date = max(
            batch["data"]["date"].max().date()
            for batch in validated_batches
            if not batch["data"].empty
        )

        update_watermark(latest_date)

        end_time = datetime.now()

        finish_run(
            run_id=run_id,
            end_time=end_time,
            status="SUCCESS",
            batches_seen=batches_seen,
            rows_inserted=rows_inserted,
            rows_updated=rows_updated,
            rows_rejected=rows_rejected
        )

        logger.info("Pipeline Completed Successfully")

    except Exception as e:

        end_time = datetime.now()

        finish_run(
            run_id=run_id,
            end_time=end_time,
            status="FAILED",
            batches_seen=0,
            rows_inserted=0,
            rows_updated=0,
            rows_rejected=0,
            error_message=str(e)
        )

        write_alert(
            pipeline="sales_etl",
            severity="CRITICAL",
            message=str(e)
        )

        logger.exception("Pipeline Failed")

        raise


def run_backfill(from_date, to_date):

    logger.info(
        f"Starting historical backfill from {from_date} to {to_date}"
    )

    start_time = datetime.now()

    run_id = create_run()

    extracted_batches = extract_data(
        last_processed_date=None,
        from_date=from_date,
        to_date=to_date
    )

    extracted_batches.sort(
        key=lambda x: x["data"]["date"].min()
    )

    total_batches = len(extracted_batches)

    if total_batches == 0:

        logger.info("No historical batches found.")

        finish_run(
            run_id=run_id,
            end_time=datetime.now(),
            status="SUCCESS",
            batches_seen=0,
            rows_inserted=0,
            rows_updated=0,
            rows_rejected=0
        )

        return

    extracted_batches = validate_batches(extracted_batches, run_id=run_id)

    if not extracted_batches:

        logger.warning("No batches passed schema validation.")

        finish_run(
            run_id=run_id,
            end_time=datetime.now(),
            status="FAILED",
            batches_seen=total_batches,
            rows_inserted=0,
            rows_updated=0,
            rows_rejected=total_batches,
            error_message="Schema validation failed"
        )

        return

    validated_batches = quality_gate(extracted_batches)

    rows_inserted = 0
    rows_updated = 0
    rows_rejected = total_batches - len(validated_batches)

    for i, batch in enumerate(validated_batches, start=1):

        transformed = transform_data([batch["data"]])

        batch["data"] = transformed[0]

        inserted, updated = load_data(
            [batch],
            run_id
        )

        rows_inserted += inserted
        rows_updated += updated

        rows_rejected += batch["report"]["rows_dropped"]

        if i % 10 == 0 or i == len(validated_batches):

            progress = (i / len(validated_batches)) * 100

            logger.info(
                f"Processed {i}/{len(validated_batches)} batches "
                f"({progress:.1f}%)"
            )

    finish_run(
        run_id=run_id,
        end_time=datetime.now(),
        status="SUCCESS",
        batches_seen=total_batches,
        rows_inserted=rows_inserted,
        rows_updated=rows_updated,
        rows_rejected=rows_rejected
    )

    logger.info("Historical backfill completed successfully.")


if __name__ == "__main__":
    run_pipeline()


# ---------------------------------------------------------------------------
# R4: generic, config-driven per-source pipeline runner.
#
# Everything above this line is the original R3 single-source (sales) flow,
# left exactly as it was - main.py still calls run_pipeline() and behaves
# identically to before. This section adds a source-agnostic runner, driven
# entirely by pipeline_config.yaml, used by the new multi-source DAG so that
# adding a third source is a YAML edit rather than a code change.
# ---------------------------------------------------------------------------

from data_contract import validate_schema_against
from quality_gate import quality_gate_generic
from transform import transform_data_generic
from load import load_data_bulk_generic
from watermark import get_watermark as _get_watermark, update_watermark as _update_watermark


def validate_batches_generic(extracted_batches, source_config, run_id=None):

    valid_batches = []

    for batch in extracted_batches:

        try:
            validate_schema_against(batch["data"], source_config.columns)
            valid_batches.append(batch)

        except Exception as e:

            logger.error(
                f"[{source_config.name}] Schema validation failed: {e}"
            )

            write_alert(
                pipeline="sales_etl",
                severity="WARN",
                message=str(e),
                batch_file=batch["file_path"].name,
                run_id=run_id,
            )

    return valid_batches


def run_source(source_config, run_id):
    """Runs extract -> schema validate -> quality gate -> transform -> bulk
    load for a single configured source. Returns a result dict the caller
    (the DAG, or run_pipeline_from_config below) uses for logging/watermarks.
    """

    watermark_name = f"sales_etl_{source_config.name}"
    last_processed_date = _get_watermark(pipeline_name=watermark_name)

    extracted_batches = extract_data(
        last_processed_date=last_processed_date,
        source_path=source_config.path,
        date_column=source_config.date_column,
    )

    batches_seen = len(extracted_batches)

    if not extracted_batches:
        logger.warning(f"[{source_config.name}] No new files found")
        return {
            "source": source_config.name,
            "batches_seen": 0,
            "rows_inserted": 0,
            "rows_updated": 0,
            "rows_rejected": 0,
            "latest_date": None,
            "status": "SUCCESS",
        }

    schema_valid = validate_batches_generic(
        extracted_batches, source_config, run_id=run_id
    )

    if not schema_valid:
        logger.warning(f"[{source_config.name}] All batches failed schema validation")
        return {
            "source": source_config.name,
            "batches_seen": batches_seen,
            "rows_inserted": 0,
            "rows_updated": 0,
            "rows_rejected": batches_seen,
            "latest_date": None,
            "status": "FAILED",
        }

    validated = quality_gate_generic(schema_valid, source_config)

    rejected_by_quality = len(schema_valid) - len(validated)

    if not validated:
        logger.warning(f"[{source_config.name}] All batches rejected by quality gate")
        return {
            "source": source_config.name,
            "batches_seen": batches_seen,
            "rows_inserted": 0,
            "rows_updated": 0,
            "rows_rejected": batches_seen,
            "latest_date": None,
            "status": "REJECTED",
        }

    data_frames = [batch["data"] for batch in validated]
    transformed = transform_data_generic(data_frames, source_config)

    for batch, df in zip(validated, transformed):
        batch["data"] = df

    rows_inserted, rows_updated = load_data_bulk_generic(
        validated, run_id, source_config
    )

    rows_dropped_in_gate = sum(
        batch["report"]["rows_dropped"] for batch in validated
    )
    rows_rejected = rejected_by_quality + rows_dropped_in_gate

    non_empty_dates = [
        batch["data"][source_config.date_column].max().date()
        for batch in validated
        if not batch["data"].empty
    ]
    latest_date = max(non_empty_dates) if non_empty_dates else None

    if latest_date:
        _update_watermark(latest_date, pipeline_name=watermark_name)

    return {
        "source": source_config.name,
        "batches_seen": batches_seen,
        "rows_inserted": rows_inserted,
        "rows_updated": rows_updated,
        "rows_rejected": rows_rejected,
        "latest_date": latest_date,
        "status": "SUCCESS",
    }


def run_pipeline_from_config(config_path=None):
    """Local (non-Airflow) convenience entrypoint: runs every configured
    source, in the order/dependency declared in pipeline_config.yaml, in a
    single process. The DAG (dags/sales_etl_dag.py) does the same thing as
    real per-source Airflow tasks with an explicit dependency chain; this
    version is for running the whole config-driven pipeline with
    `python -m etl.src.pipeline` style local invocation, e.g. for the
    idempotency/backfill checks in scripts/.
    """

    from config_loader import load_pipeline_config

    config = load_pipeline_config(config_path)

    run_id = create_run()
    start_time = datetime.now()

    results = []

    try:
        for source_config in config.sources:
            logger.info(f"Running source: {source_config.name}")
            results.append(run_source(source_config, run_id))

        total_batches = sum(r["batches_seen"] for r in results)
        total_inserted = sum(r["rows_inserted"] for r in results)
        total_updated = sum(r["rows_updated"] for r in results)
        total_rejected = sum(r["rows_rejected"] for r in results)

        overall_status = "SUCCESS"
        if any(r["status"] == "FAILED" for r in results):
            overall_status = "FAILED"
        elif all(r["status"] == "REJECTED" for r in results):
            overall_status = "REJECTED"

        finish_run(
            run_id=run_id,
            end_time=datetime.now(),
            status=overall_status,
            batches_seen=total_batches,
            rows_inserted=total_inserted,
            rows_updated=total_updated,
            rows_rejected=total_rejected,
        )

        logger.info(f"Config-driven pipeline run {run_id} finished: {results}")

        return results

    except Exception as e:

        finish_run(
            run_id=run_id,
            end_time=datetime.now(),
            status="FAILED",
            batches_seen=0,
            rows_inserted=0,
            rows_updated=0,
            rows_rejected=0,
            error_message=str(e),
        )

        write_alert(
            pipeline="sales_etl",
            severity="CRITICAL",
            message=str(e),
            run_id=run_id,
        )

        logger.exception("Config-driven pipeline failed")

        raise