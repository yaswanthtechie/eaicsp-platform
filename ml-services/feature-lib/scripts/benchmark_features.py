import time

import pandas as pd

from src.build_features import build_all_features
from src.feature_quality import score_feature_quality

WAREHOUSES = 100
DAYS_PER_WAREHOUSE = 1_000

df = pd.DataFrame(
    {
        "warehouse": [
            warehouse
            for warehouse in range(WAREHOUSES)
            for _ in range(DAYS_PER_WAREHOUSE)
        ],
        "date": list(
            pd.date_range(
                "2020-01-01",
                periods=DAYS_PER_WAREHOUSE,
                freq="D",
            )
        )
        * WAREHOUSES,
        "target": range(WAREHOUSES * DAYS_PER_WAREHOUSE),
    }
)

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