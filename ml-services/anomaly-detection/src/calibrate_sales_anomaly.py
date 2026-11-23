"""
Calibrate Z_SPIKE on a clean sales file (no planted anomalies).

Picks the z value that gives a false-alarm budget of 2 per 1000 scored days
(spike and drop false alarms together), so the number can be regenerated
when the client data arrives.

Run: python -m src.calibrate_sales_anomaly <seed out>/sales_daily.csv
"""

import argparse
import math

import numpy as np
import pandas as pd

from src.config import FALSE_ALARM_BUDGET, MIN_CALIBRATION_DAYS, SPIKE_MEDIUM
from src.sales_anomaly import detect, normalize_columns


def calibrate(df, budget=FALSE_ALARM_BUDGET):
    """Return (drop_rate, z_spike) for a clean sales frame."""

    dates = normalize_columns(df)["date"]
    span_days = (dates.max() - dates.min()).days + 1 if len(dates) else 0

    if span_days < MIN_CALIBRATION_DAYS:
        raise ValueError(
            f"The file covers {span_days} days. Calibrate on at least three "
            f"months ({MIN_CALIBRATION_DAYS} days) of clean data."
        )

    # Score every day with spikes switched off, so only drops are flagged.
    scores, _ = detect(df, z_spike=np.inf)
    scored = scores[scores["score"].notna()]

    if scored.empty:
        raise ValueError(
            "No series has enough history to score (8 weeks of data plus 4 "
            "weeks of baseline). Calibrate on at least three months of clean data."
        )

    drop_rate = float((scored["direction"] == "drop").mean())

    if drop_rate >= budget:
        raise ValueError(
            f"Drop false alarms alone are {1000 * drop_rate:.2f} per 1000 days, "
            f"over the budget of {1000 * budget:.2f}. Review DROP_LOW and "
            "DROP_MIN_EXPECTED before calibrating Z_SPIKE."
        )

    z_spike = float(np.quantile(scored["score"], 1 - (budget - drop_rate)))

    if not z_spike < SPIKE_MEDIUM:
        raise ValueError(
            f"Calibrated z_spike {z_spike:.2f} is not below SPIKE_MEDIUM "
            f"({SPIKE_MEDIUM}). Raise SPIKE_MEDIUM and SPIKE_HIGH in config.py "
            "before using it, or no spike would ever be low."
        )

    return drop_rate, z_spike


def main(argv=None):

    parser = argparse.ArgumentParser(
        description="Calibrate Z_SPIKE on a clean sales file."
    )
    parser.add_argument(
        "sales_csv", help="Clean sales file, e.g. <seed out>/sales_daily.csv"
    )
    args = parser.parse_args(argv)

    drop_rate, z_spike = calibrate(pd.read_csv(args.sales_csv, dtype=str))

    print(f"drop false alarms per 1000: {1000 * drop_rate:.2f}")
    # Round up, never down: a lower threshold flags more than the budget.
    print(f"Z_SPIKE = {math.ceil(z_spike * 10) / 10:.1f} (quantile {z_spike:.3f})")


if __name__ == "__main__":
    main()
