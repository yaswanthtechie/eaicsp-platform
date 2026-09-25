import time

import numpy as np
import pandas as pd

from src.build_features import build_all_features
from src.feature_quality import score_feature_quality


WAREHOUSES = 100
DAYS_PER_WAREHOUSE = 1_000
NEW_WAREHOUSE_DAYS = 60


dates = pd.date_range(
    "2020-01-01",
    periods=DAYS_PER_WAREHOUSE,
    freq="D",
)

rows = []

rng = np.random.default_rng(42)

for warehouse in range(WAREHOUSES):
    weekend = dates.dayofweek >= 5
    demand_lambda = np.where(weekend, 60, 50)
    target = rng.poisson(demand_lambda)

    for date, value in zip(dates, target):
        rows.append(
            {
                "warehouse": warehouse,
                "date": date,
                "target": value,
            }
        )

df = pd.DataFrame(rows)

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
    group_cols=["warehouse"],
    feature_version="v1",
)

elapsed = time.perf_counter() - start

print(f"Rows processed: {len(df):,}")
print(f"Warehouses: {WAREHOUSES}")
print(f"Days per warehouse: {DAYS_PER_WAREHOUSE}")
print(f"Features generated: {len(features.columns)}")
print(f"Execution time: {elapsed:.4f} seconds")

quality = score_feature_quality(features)

print("\nRisky features:")
print(quality[quality["risk"] == "risky"])


new_warehouse_df = (
    df.groupby("warehouse", group_keys=False)
    .head(NEW_WAREHOUSE_DAYS)
    .copy()
)

new_warehouse_features = build_all_features(
    df=new_warehouse_df,
    date_col="date",
    target_col="target",
    config=config,
    group_cols=["warehouse"],
    feature_version="v1",
)

new_warehouse_quality = score_feature_quality(
    new_warehouse_features
)

print(
    f"\nRisky features with only "
    f"{NEW_WAREHOUSE_DAYS} days of history:"
)

print(
    new_warehouse_quality[
        new_warehouse_quality["risk"] == "risky"
    ]
)