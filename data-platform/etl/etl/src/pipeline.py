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
            return

        data_frames = [
            batch["data"]
            for batch in extracted_batches
        ]

        transformed_data = transform_data(data_frames)

        for batch, df in zip(extracted_batches, transformed_data):
            batch["data"] = df

        validated_data = quality_gate(extracted_batches)

        if not validated_data:
            logger.warning("No valid data")
            return

        rows_loaded = sum(len(df) for df in validated_data)

        load_data(validated_data)

        latest_date = max(
            df["date"].max().date()
            for df in validated_data
        )

        update_watermark(latest_date)

        end_time = datetime.now()

        log_success(
            start_time,
            end_time,
            rows_loaded
        )

        logger.info("Pipeline Completed Successfully")

    except Exception as e:

        end_time = datetime.now()

        log_failure(
            start_time,
            end_time,
            str(e)
        )

        logger.exception("Pipeline Failed")

        raise


if __name__ == "__main__":
    run_pipeline()