from pathlib import Path
import pandas as pd

from alert_service import write_alert
from logging_config import logger


def extract_data(
    last_processed_date=None,
    from_date=None,
    to_date=None,
    source_path="data/batches/sales",
    date_column="date",
):

    batch_folder = Path(source_path)

    csv_files = sorted(batch_folder.glob("*.csv"))

    batches = []

    for file in csv_files:

        try:
            df = pd.read_csv(file)

            if df.empty:
                continue

            df[date_column] = pd.to_datetime(df[date_column])


            if last_processed_date is not None:
                df = df[df[date_column].dt.date >= last_processed_date]


            if from_date is not None and to_date is not None:
                df = df[
                    (df[date_column].dt.date >= from_date)
                    & (df[date_column].dt.date <= to_date)
                ]

            if df.empty:
                continue

            batches.append(
                {
                    "file_path": file,
                    "data": df
                }
            )

        except Exception as e:

            logger.error(f"Failed to extract {file.name}: {e}")

            write_alert(
                pipeline="sales_etl",
                severity="WARN",
                message=f"Extract failed: {e}",
                batch_file=file.name
            )

            continue

    return batches