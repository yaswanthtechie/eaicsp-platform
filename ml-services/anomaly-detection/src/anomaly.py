# Intentionally planting 20 anomalies in the data to test the anomaly detection system.

from pathlib import Path

import numpy as np
import pandas as pd

project_root = Path(__file__).resolve().parent.parent
output_dir = project_root / "output"
output_dir.mkdir(parents=True, exist_ok=True)

np.random.seed(42)
n = 5000

anomaly_idx = np.random.choice(n, size=20, replace=False)

df = pd.read_csv(output_dir / "sensor_readings.csv")

df.loc[anomaly_idx, "temperature"] += np.random.uniform(8, 15, 20)

df['is_anomaly'] = 0
df.loc[anomaly_idx, 'is_anomaly'] = 1

df.to_csv(output_dir / "sensor_readings_with_anomalies.csv", index=False)

print("Anomaly indices:", anomaly_idx)
print("-" * 50 )
print("Anomalies planted in the data")
print("-" * 50 )
print(df["is_anomaly"].value_counts())
