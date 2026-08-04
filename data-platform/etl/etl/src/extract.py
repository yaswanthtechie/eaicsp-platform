from pathlib import Path
import pandas as pd


def extract_data(last_processed_date=None, from_date=None, to_date=None):

    batch_folder = Path("data/batches")

    csv_files = sorted(batch_folder.glob("*.csv"))

    batches = []

    for file in csv_files:

        df = pd.read_csv(file)

        if df.empty:
            continue

        df["date"] = pd.to_datetime(df["date"])

        
        if last_processed_date is not None:
            df = df[df["date"].dt.date >= last_processed_date]

        
        if from_date is not None and to_date is not None:
            df = df[
                (df["date"].dt.date >= from_date)
                & (df["date"].dt.date <= to_date)
            ]

        if df.empty:
            continue

        batches.append(
            {
                "file_path": file,
                "data": df
            }
        )

    return batches