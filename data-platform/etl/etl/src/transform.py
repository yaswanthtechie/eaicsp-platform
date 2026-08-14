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