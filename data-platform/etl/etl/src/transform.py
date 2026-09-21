import pandas as pd

from alert_service import write_alert
from logging_config import logger


def transform_data(data_frames):

    transformed_data = []

    try:

        for df in data_frames:

            clean_df = df.copy()

            clean_df = clean_df.drop_duplicates()

            clean_df["date"] = pd.to_datetime(clean_df["date"])

            clean_df["quantity_sold"] = clean_df["quantity_sold"].astype(int)

            clean_df["unit_price"] = clean_df["unit_price"].astype(float)

            transformed_data.append(clean_df)

    except Exception as e:

        logger.error(f"Transform stage failed: {e}")

        write_alert(
            pipeline="sales_etl",
            severity="CRITICAL",
            message=f"Transform stage failed: {e}"
        )

        raise

    return transformed_data


def transform_data_generic(data_frames, source_config):
    """Same shape as transform_data(), but date column and dtype casts come
    from the source's config instead of being hardcoded to sales columns."""

    transformed_data = []

    try:

        for df in data_frames:

            clean_df = df.copy()

            clean_df = clean_df.drop_duplicates()

            clean_df[source_config.date_column] = pd.to_datetime(
                clean_df[source_config.date_column]
            )

            for col in source_config.integer_columns:
                clean_df[col] = clean_df[col].astype(int)

            for col in source_config.numeric_columns:
                clean_df[col] = clean_df[col].astype(float)

            transformed_data.append(clean_df)

    except Exception as e:

        logger.error(f"Transform stage failed for {source_config.name}: {e}")

        write_alert(
            pipeline="sales_etl",
            severity="CRITICAL",
            message=f"Transform stage failed for {source_config.name}: {e}"
        )

        raise

    return transformed_data