import pandas as pd
import json

from src.profiler import Profiler


# Load old and new datasets
df_old = pd.read_csv("data/sales_data.csv")
df_new = pd.read_csv("data/sales_data_new.csv")

# Create profiler
profiler = Profiler()

# Test profiling
report = profiler.profile(df_old)

print("Profiler API working successfully!")

# Test JSON serialization
json.dumps(report)

print("JSON serialization working successfully!")

# Test drift comparison
drift = profiler.compare(df_old, df_new)

print("Drift comparison working successfully!")
print("Drift Status:", drift["status"])