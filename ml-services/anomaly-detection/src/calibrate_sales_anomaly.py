"""
Calibrate Z_SPIKE on a clean sales file (no planted anomalies).

Picks the z value that gives a false-alarm budget of 2 per 1000 scored days
(spike and drop false alarms together), so the number can be regenerated
when the client data arrives.

Run: python -m src.calibrate_sales_anomaly <seed out>/sales_daily.csv
"""

import sys

import numpy as np
import pandas as pd

import src.sales_anomaly as sa

BUDGET = 2 / 1000  # false alarms per scored day on the clean seed

sa.Z_SPIKE = np.inf  # score every day, flag no spikes
scores, _ = sa.detect(pd.read_csv(sys.argv[1]))
s = scores[scores["score"].notna()]

drop_rate = (
    (s["quantity"] <= sa.DROP_LOW * s["expected"])
    & (s["expected"] >= sa.DROP_MIN_EXPECTED)
).mean()

z_spike = np.quantile(s["score"], 1 - (BUDGET - drop_rate))
print(f"drop false alarms per 1000: {1000 * drop_rate:.2f}")
print(f"Z_SPIKE = {z_spike:.1f}")