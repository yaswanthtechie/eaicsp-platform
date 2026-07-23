from pathlib import Path

import numpy as np
import pandas as pd

project_root = Path(__file__).resolve().parent.parent
output_dir = project_root / "output"
output_dir.mkdir(parents=True, exist_ok=True)

np.random.seed(42)  # Making random state constant

n = 5000  # Number of data points

df = pd.DataFrame({'timestamp': pd.date_range(start='2026-01-01', periods=n, freq='5min'),
                   'temperature': np.random.normal(loc=22, scale=1.5, size=n),
                   'humidity': np.random.normal(loc=45, scale=5, size=n),
                   'stock_count': np.random.normal(loc=500, scale=30, size=n)})  
  
# loc is the mean and scale is the standard deviation

df.to_csv(output_dir / "sensor_readings.csv", index=False)
print("Data generated")
