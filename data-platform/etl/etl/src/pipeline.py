from datetime import datetime
from pathlib import Path
import time

import numpy as np
import pandas as pd

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


# ============================================================================
# SHARED VALIDATION
# ============================================================================

def validate_batches(extracted_batches, run_id=None):
    """
    Validate extracted batches against:
        1. Data contract
        2. Pandera schema
        3. Schema drift detection

    Batches that fail schema validation are excluded from further processing.
    """

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
                run_id=run_id,
            )

    return valid_batches


# ============================================================================
# AIRFLOW XCOM SERIALIZATION HELPERS
# ============================================================================

def _json_safe(value):
    """Convert Pandas/NumPy values into Airflow XCom JSON-safe values."""

    if value is None:
        return None

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()

    if isinstance(value, pd.Timedelta):
        return value.total_seconds()

    if isinstance(value, np.generic):
        return _json_safe(value.item())

    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]

    if isinstance(value, float) and np.isnan(value):
        return None

    return value


def serialize_batches(batches):
    """
    Convert batches containing DataFrames and Path objects into
    JSON-safe structures for Airflow XCom.
    """

    serialized = []

    for batch in batches:
        data = batch["data"].copy()

        # Convert missing values to None before serialization.
        data = data.astype(object).where(pd.notna(data), None)

        records = data.to_dict(orient="records")

        serialized.append(
            _json_safe(
                {
                    "file_path": str(batch["file_path"]),
                    "data": records,
                    "report": batch.get("report"),
                }
            )
        )

    return serialized


def deserialize_batches(serialized_batches):
    """Reconstruct batches from XCom-safe structures."""

    deserialized = []

    for item in serialized_batches or []:
        batch = {
            "file_path": Path(item["file_path"]),
            "data": pd.DataFrame(item["data"]),
        }

        if item.get("report") is not None:
            batch["report"] = item["report"]

        # Restore the date column to datetime for downstream processing.
        if "date" in batch["data"].columns:
            batch["data"]["date"] = pd.to_datetime(
                batch["data"]["date"],
                errors="coerce",
            )

        deserialized.append(batch)

    return deserialized


# ============================================================================
# AIRFLOW STAGE 1
# EXTRACT
# ============================================================================

def extract_airflow_task(**context):
    """
    Airflow extract stage.

    Responsibilities:
        - Create pipeline run
        - Read watermark
        - Extract new batches
        - Validate schema
        - Return only JSON-safe XCom data
    """

    ti = context["ti"]

    run_id = create_run()

    ti.xcom_push(key="run_id", value=run_id)

    last_processed_date = get_watermark()

    logger.info(
        f"Starting extraction from watermark: {last_processed_date}"
    )

    extracted_batches = extract_data(last_processed_date)

    batches_seen = len(extracted_batches)

    ti.xcom_push(key="batches_seen", value=batches_seen)

    if not extracted_batches:
        logger.warning("No new files found")
        return []

    schema_valid_batches = validate_batches(
        extracted_batches,
        run_id=run_id,
    )

    logger.info(
        f"Extracted {batches_seen} batches; "
        f"{len(schema_valid_batches)} passed schema validation"
    )

    return serialize_batches(schema_valid_batches)


# ============================================================================
# AIRFLOW STAGE 2
# QUALITY GATE + BRANCH
# ============================================================================

def quality_gate_airflow_task(**context):
    """Run quality gate and branch to load or reject_and_notify."""

    ti = context["ti"]

    serialized_batches = ti.xcom_pull(task_ids="extract")
    schema_valid_batches = deserialize_batches(serialized_batches)

    if not schema_valid_batches:
        logger.warning("All batches failed schema validation")

        ti.xcom_push(
            key="rows_rejected_pre_load",
            value=0,
        )

        return "reject_and_notify"

    validated_batches = quality_gate(schema_valid_batches)

    rejected_by_quality = (
        len(schema_valid_batches) - len(validated_batches)
    )

    ti.xcom_push(
        key="rows_rejected_pre_load",
        value=rejected_by_quality,
    )

    if not validated_batches:
        logger.warning("All batches rejected by the quality gate")
        return "reject_and_notify"

    ti.xcom_push(
        key="validated_batches",
        value=serialize_batches(validated_batches),
    )

    logger.info(
        f"{len(validated_batches)} batches passed quality gate"
    )

    return "load"


# ============================================================================
# AIRFLOW STAGE 3A
# LOAD
# ============================================================================

def load_airflow_task(**context):
    """Transform validated batches and load them into PostgreSQL."""

    ti = context["ti"]

    run_id = ti.xcom_pull(
        task_ids="extract",
        key="run_id",
    )

    serialized_batches = ti.xcom_pull(
        task_ids="quality_gate",
        key="validated_batches",
    )

    validated_batches = deserialize_batches(serialized_batches)

    if not validated_batches:
        logger.warning("No validated batches available for loading")

        ti.xcom_push(key="rows_inserted", value=0)
        ti.xcom_push(key="rows_updated", value=0)
        ti.xcom_push(key="rows_rejected", value=0)
        ti.xcom_push(key="latest_date", value=None)
        ti.xcom_push(key="status", value="SUCCESS")

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
        run_id,
    )

    rows_dropped_in_gate = sum(
        batch.get("report", {}).get("rows_dropped", 0)
        for batch in validated_batches
    )

    rejected_pre_load = ti.xcom_pull(
        task_ids="quality_gate",
        key="rows_rejected_pre_load",
    ) or 0

    rows_rejected = rejected_pre_load + rows_dropped_in_gate

    non_empty_dates = [
        batch["data"]["date"].max().date()
        for batch in validated_batches
        if not batch["data"].empty
    ]

    latest_date = max(non_empty_dates) if non_empty_dates else None

    ti.xcom_push(key="rows_inserted", value=rows_inserted)
    ti.xcom_push(key="rows_updated", value=rows_updated)
    ti.xcom_push(key="rows_rejected", value=rows_rejected)
    ti.xcom_push(
        key="latest_date",
        value=latest_date.isoformat() if latest_date else None,
    )
    ti.xcom_push(key="status", value="SUCCESS")

    logger.info(
        f"Loaded batches. "
        f"Inserted={rows_inserted}, "
        f"Updated={rows_updated}, "
        f"Rejected={rows_rejected}"
    )


# ============================================================================
# AIRFLOW STAGE 3B
# REJECT + NOTIFY
# ============================================================================

def reject_and_notify_airflow_task(**context):
    """Handle runs where no data survives validation or quality checks."""

    ti = context["ti"]

    run_id = ti.xcom_pull(
        task_ids="extract",
        key="run_id",
    )

    batches_seen = ti.xcom_pull(
        task_ids="extract",
        key="batches_seen",
    ) or 0

    message = (
        "No batches to process"
        if batches_seen == 0
        else "All batches failed schema or quality validation"
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
        key="latest_date",
        value=None,
    )

    ti.xcom_push(
        key="status",
        value="SUCCESS" if batches_seen == 0 else "REJECTED",
    )


# ============================================================================
# AIRFLOW STAGE 4
# UPDATE WATERMARK
# ============================================================================

def update_watermark_airflow_task(**context):
    """Advance watermark only when the load branch produced a date."""

    ti = context["ti"]

    latest_date = ti.xcom_pull(
        task_ids="load",
        key="latest_date",
    )

    if not latest_date:
        logger.info(
            "Skipping watermark update: "
            "no rows were loaded this run"
        )
        return

    watermark_date = datetime.fromisoformat(latest_date).date()

    update_watermark(watermark_date)

    logger.info(
        f"Watermark advanced to {watermark_date}"
    )


# ============================================================================
# AIRFLOW STAGE 5
# LOG RUN
# ============================================================================

def log_run_airflow_task(**context):
    """Write the final pipeline audit record."""

    ti = context["ti"]

    run_id = ti.xcom_pull(
        task_ids="extract",
        key="run_id",
    )

    batches_seen = ti.xcom_pull(
        task_ids="extract",
        key="batches_seen",
    ) or 0

    rows_inserted = ti.xcom_pull(
        task_ids="load",
        key="rows_inserted",
    ) or 0

    rows_updated = ti.xcom_pull(
        task_ids="load",
        key="rows_updated",
    ) or 0

    rows_rejected = ti.xcom_pull(
        task_ids="load",
        key="rows_rejected",
    )

    status = ti.xcom_pull(
        task_ids="load",
        key="status",
    )

    if rows_rejected is None:
        rows_rejected = ti.xcom_pull(
            task_ids="reject_and_notify",
            key="rows_rejected",
        ) or 0

    if status is None:
        status = ti.xcom_pull(
            task_ids="reject_and_notify",
            key="status",
        )

    if status is None:
        status = "FAILED"

    finish_run(
        run_id=run_id,
        end_time=datetime.now(),
        status=status,
        batches_seen=batches_seen,
        rows_inserted=rows_inserted,
        rows_updated=rows_updated,
        rows_rejected=rows_rejected,
    )

    logger.info(
        f"Pipeline run {run_id} finished with status={status}"
    )


# ============================================================================
# ORIGINAL NON-AIRFLOW PIPELINE
# ============================================================================

def run_pipeline():
    run_id = create_run()

    try:
        logger.info("Pipeline Started")

        last_processed_date = get_watermark()
        extracted_batches = extract_data(last_processed_date)

        if not extracted_batches:
            logger.warning("No new files found")

            finish_run(
                run_id=run_id,
                end_time=datetime.now(),
                status="SUCCESS",
                batches_seen=0,
                rows_inserted=0,
                rows_updated=0,
                rows_rejected=0,
            )
            return

        batches_seen = len(extracted_batches)

        extracted_batches = validate_batches(
            extracted_batches,
            run_id=run_id,
        )

        if not extracted_batches:
            logger.warning("All batches failed schema validation")

            finish_run(
                run_id=run_id,
                end_time=datetime.now(),
                status="FAILED",
                batches_seen=batches_seen,
                rows_inserted=0,
                rows_updated=0,
                rows_rejected=batches_seen,
                error_message="Schema validation failed",
            )
            return

        validated_batches = quality_gate(extracted_batches)

        rejected_batches = (
            batches_seen - len(validated_batches)
        )

        if not validated_batches:
            logger.warning("All batches rejected")

            finish_run(
                run_id=run_id,
                end_time=datetime.now(),
                status="REJECTED",
                batches_seen=batches_seen,
                rows_inserted=0,
                rows_updated=0,
                rows_rejected=rejected_batches,
                error_message="All batches rejected",
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
            run_id,
        )

        rows_rejected = (
            rejected_batches
            + sum(
                batch["report"]["rows_dropped"]
                for batch in validated_batches
            )
        )

        latest_date = max(
            batch["data"]["date"].max().date()
            for batch in validated_batches
            if not batch["data"].empty
        )

        update_watermark(latest_date)

        finish_run(
            run_id=run_id,
            end_time=datetime.now(),
            status="SUCCESS",
            batches_seen=batches_seen,
            rows_inserted=rows_inserted,
            rows_updated=rows_updated,
            rows_rejected=rows_rejected,
        )

        logger.info("Pipeline Completed Successfully")

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
        )

        logger.exception("Pipeline Failed")
        raise


# ============================================================================
# BACKFILL
# ============================================================================

def run_backfill(from_date, to_date):
    logger.info(
        f"Starting historical backfill "
        f"from {from_date} to {to_date}"
    )

    run_id = create_run()

    extracted_batches = extract_data(
        last_processed_date=None,
        from_date=from_date,
        to_date=to_date,
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
            rows_rejected=0,
        )
        return

    extracted_batches = validate_batches(
        extracted_batches,
        run_id=run_id,
    )

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
            error_message="Schema validation failed",
        )
        return

    validated_batches = quality_gate(extracted_batches)

    rows_inserted = 0
    rows_updated = 0
    rows_rejected = total_batches - len(validated_batches)

    start_time = time.perf_counter()

    for i, batch in enumerate(validated_batches, start=1):
        transformed = transform_data([batch["data"]])
        batch["data"] = transformed[0]

        inserted, updated = load_data(
            [batch],
            run_id,
        )

        rows_inserted += inserted
        rows_updated += updated

        rows_rejected += batch["report"]["rows_dropped"]

        if i % 10 == 0 or i == len(validated_batches):
            total = len(validated_batches)
            progress = (i / total) * 100

            elapsed = time.perf_counter() - start_time
            eta_seconds = (elapsed / i) * (total - i) if i else 0

            logger.info(
                f"Processed {i}/{total} batches "
                f"({progress:.1f}%). ETA {eta_seconds / 60:.0f}m"
            )

    finish_run(
        run_id=run_id,
        end_time=datetime.now(),
        status="SUCCESS",
        batches_seen=total_batches,
        rows_inserted=rows_inserted,
        rows_updated=rows_updated,
        rows_rejected=rows_rejected,
    )

    logger.info("Historical backfill completed successfully.")


if __name__ == "__main__":
    run_pipeline()