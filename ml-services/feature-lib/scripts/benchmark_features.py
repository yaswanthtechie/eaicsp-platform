import time

import pandas as pd

from src.build_features import build_all_features


ROWS = 100_000

df = pd.DataFrame({
    "date": pd.date_range("2020-01-01", periods=ROWS, freq="D"),
    "target": range(ROWS),
})

config = {
    "lags": [1, 7, 30],
    "windows": [7, 30],
}

start = time.perf_counter()

features = build_all_features(
    df=df,
    date_col="date",
    target_col="target",
    config=config,
    feature_version="v1",
)

elapsed = time.perf_counter() - start

print(f"Rows processed: {len(df):,}")
print(f"Features generated: {len(features.columns)}")
print(f"Execution time: {elapsed:.4f} seconds")