from datetime import datetime

from extract import extract_data
from transform import transform_data
from quality_gate import quality_gate
from load import load_data
from watermark import get_watermark, update_watermark
from logger import log_success, log_failure
from logging_config import logger


def run_pipeline():

    start_time = datetime.now()

    try:

        logger.info("Pipeline Started")

        last_processed_date = get_watermark()

        extracted_batches = extract_data(last_processed_date)

        if not extracted_batches:

            logger.warning("No new files found")

            end_time = datetime.now()

            log_success(
                start_time,
                end_time,
                batches_seen=0,
                rows_inserted=0,
                rows_updated=0,
                rows_rejected=0
            )

            return

        batches_seen = len(extracted_batches)

        validated_batches = quality_gate(extracted_batches)

        rows_rejected = batches_seen - len(validated_batches)

        if not validated_batches:

            logger.warning("No valid data")

            end_time = datetime.now()

            log_success(
                start_time,
                end_time,
                batches_seen=batches_seen,
                rows_inserted=0,
                rows_updated=0,
                rows_rejected=rows_rejected
            )

            return

        data_frames = [
            batch["data"]
            for batch in validated_batches
        ]

        transformed_data = transform_data(data_frames)

        for batch, df in zip(validated_batches, transformed_data):

            batch["data"] = df

        rows_loaded = sum(
            len(batch["data"])
            for batch in validated_batches
        )

        load_data(validated_batches)

        latest_date = max(
            batch["data"]["date"].max().date()
            for batch in validated_batches
        )

        update_watermark(latest_date)

        end_time = datetime.now()

        log_success(
            start_time,
            end_time,
            batches_seen=batches_seen,
            rows_inserted=rows_loaded,
            rows_updated=0,
            rows_rejected=rows_rejected
        )

        logger.info("Pipeline Completed Successfully")

    except Exception as e:

        end_time = datetime.now()

        log_failure(
            start_time,
            end_time,
            str(e),
            batches_seen=0,
            rows_inserted=0,
            rows_updated=0,
            rows_rejected=0
        )

        logger.exception("Pipeline Failed")

        raise


if __name__ == "__main__":
    run_pipeline()