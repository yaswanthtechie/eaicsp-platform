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


 

def validate_batches(extracted_batches):

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
                batch_file=batch["file_path"].name
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

        extracted_batches = validate_batches(extracted_batches)

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

    extracted_batches = validate_batches(extracted_batches)

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