from pathlib import Path
import pandas as pd


def extract_data(last_processed_date):

    batch_folder = Path("data/batches")

    csv_files = sorted(batch_folder.glob("*.csv"))

    batches = []

    for file in csv_files:

        df = pd.read_csv(file)

        df["date"] = pd.to_datetime(df["date"])

        df = df[df["date"].dt.date > last_processed_date]

        if not df.empty:

            batches.append(
                {
                    "file_path": file,
                    "data": df
                }
            )

    return batches