"""
Calibrate Z_SPIKE on a clean sales file (no planted anomalies).

Picks the z value that gives a false-alarm budget of 2 per 1000 scored days
(spike and drop false alarms together), so the number can be regenerated
when the client data arrives.

Run: python -m src.calibrate_sales_anomaly <seed out>/sales_daily.csv
"""

import argparse

import numpy as np
import pandas as pd

from src.sales_anomaly import detect

BUDGET = 2 / 1000  # false alarms per scored day on the clean file


def calibrate(df, budget=BUDGET):
    """Return (drop_rate, z_spike) for a clean sales frame."""

    # Score every day with spikes switched off, so only drops are flagged.
    scores, _ = detect(df, z_spike=np.inf)
    scored = scores[scores["score"].notna()]

    drop_rate = float((scored["direction"] == "drop").mean())

    if drop_rate >= budget:
        raise ValueError(
            f"Drop false alarms alone are {1000 * drop_rate:.2f} per 1000 days, "
            f"over the budget of {1000 * budget:.2f}. Review DROP_LOW and "
            "DROP_MIN_EXPECTED before calibrating Z_SPIKE."
        )

    z_spike = float(np.quantile(scored["score"], 1 - (budget - drop_rate)))

    return drop_rate, z_spike


def main(argv=None):

    parser = argparse.ArgumentParser(description="Calibrate Z_SPIKE on a clean sales file.")
    parser.add_argument("sales_csv", help="Clean sales file, e.g. <seed out>/sales_daily.csv")
    args = parser.parse_args(argv)

    drop_rate, z_spike = calibrate(pd.read_csv(args.sales_csv, dtype=str))

    print(f"drop false alarms per 1000: {1000 * drop_rate:.2f}")
    print(f"Z_SPIKE = {z_spike:.1f}")


if __name__ == "__main__":
    main()