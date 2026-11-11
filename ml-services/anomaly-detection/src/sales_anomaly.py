"""
Sales anomaly detection: unusual spikes and drops per product and warehouse.

Input: sales history with columns sale_date, product_code (or sku_id),
warehouse (or warehouse_id), quantity_sold. One daily series per product and
warehouse (rows for the same day are summed).

Method: seasonal-naive baseline + robust z-score (see README).

    expected(t) = median of the same weekday over the previous 8 weeks
                  (values at t-7, t-14, ..., t-56; at least 4 needed)
    scale(t)    = max(1.4826 * MAD of those values, sqrt(expected), 1)
    z(t)        = (quantity(t) - expected(t)) / scale(t)

Only strictly earlier days are used: a day's score never depends on that
day's future. Thresholds are fixed design values, not tuned on any result.

Run (from ml-services/anomaly-detection):
    python -m src.sales_anomaly --input <sales.csv> --output output/sales_anomalies.csv
"""

import argparse
import logging
import warnings
from pathlib import Path

import numpy as np
import pandas as pd


log = logging.getLogger(__name__)

LOOKBACK_WEEKS = 8
MIN_WEEKS = 4
MIN_SERIES_DAYS = 56

Z_LOW = 3.5
Z_MEDIUM = 5.0
Z_HIGH = 8.0

COLUMN_ALIASES = {
    "date": ("sale_date", "date"),
    "product": ("product_code", "sku_id", "sku"),
    "warehouse": ("warehouse", "warehouse_id"),
    "quantity": ("quantity_sold", "quantity"),
}

OUTPUT_COLUMNS = [
    "product",
    "warehouse",
    "date",
    "quantity",
    "expected",
    "scale",
    "score",
    "is_anomaly",
    "severity",
    "direction",
]


def normalize_columns(df):
    """Return a frame with columns date, product, warehouse, quantity."""

    picked = {}

    for name, aliases in COLUMN_ALIASES.items():
        found = next((a for a in aliases if a in df.columns), None)

        if found is None:
            raise ValueError(
                f"No {name} column. Expected one of {aliases}; "
                f"got {list(df.columns)}."
            )

        picked[name] = found

    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df[picked["date"]], errors="coerce"),
            "product": df[picked["product"]].astype(str),
            "warehouse": df[picked["warehouse"]].astype(str),
            "quantity": pd.to_numeric(df[picked["quantity"]], errors="coerce"),
        }
    )

    bad = out["date"].isna() | out["quantity"].isna()

    if bad.any():
        log.warning("Dropping %d rows with an invalid date or quantity.", int(bad.sum()))
        out = out[~bad]

    out["date"] = out["date"].dt.normalize()

    return out


def severity_for_score(score):
    """high / medium / low from |z|; empty string if not an anomaly."""

    a = abs(score)

    if not np.isfinite(a) or a < Z_LOW:
        return ""

    if a >= Z_HIGH:
        return "high"

    if a >= Z_MEDIUM:
        return "medium"

    return "low"


def score_series(values):
    """
    Return (expected, scale, z) for a daily series (arrays of length n).

    z is NaN for days with fewer than MIN_WEEKS same-weekday values of
    history. Uses only values strictly before each day.
    """

    v = np.asarray(values, dtype=float)
    n = len(v)

    lagged = np.full((n, LOOKBACK_WEEKS), np.nan)

    for k in range(1, LOOKBACK_WEEKS + 1):
        lag = 7 * k

        if lag < n:
            lagged[lag:, k - 1] = v[: n - lag]

    count = np.sum(~np.isnan(lagged), axis=1)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        expected = np.nanmedian(lagged, axis=1)
        mad = np.nanmedian(np.abs(lagged - expected[:, None]), axis=1)

    scale = np.maximum.reduce(
        [1.4826 * mad, np.sqrt(np.maximum(expected, 1.0)), np.ones(n)]
    )

    z = (v - expected) / scale
    z[count < MIN_WEEKS] = np.nan

    return expected, scale, z


def detect(df, fill_missing_as_zero=True):
    """
    Score every product/warehouse series.

    Returns (scores, skipped). scores has one row per scored day (see
    OUTPUT_COLUMNS). skipped lists (product, warehouse, days) for series
    shorter than MIN_SERIES_DAYS; each gets a log line and no flags.
    """

    data = normalize_columns(df)
    frames = []
    skipped = []

    for (product, warehouse), group in data.groupby(
        ["product", "warehouse"], sort=True
    ):
        daily = group.groupby("date")["quantity"].sum()
        daily = daily.reindex(
            pd.date_range(daily.index.min(), daily.index.max(), freq="D")
        )

        if fill_missing_as_zero:
            daily = daily.fillna(0.0)

        if len(daily) < MIN_SERIES_DAYS:
            log.warning(
                "Skipping %s / %s: %d days of data, need at least %d (8 weeks).",
                product,
                warehouse,
                len(daily),
                MIN_SERIES_DAYS,
            )
            skipped.append((product, warehouse, len(daily)))
            continue

        expected, scale, z = score_series(daily.to_numpy())
        abs_z = np.abs(z)
        flagged = abs_z >= Z_LOW

        frames.append(
            pd.DataFrame(
                {
                    "product": product,
                    "warehouse": warehouse,
                    "date": daily.index,
                    "quantity": daily.to_numpy(),
                    "expected": expected,
                    "scale": scale,
                    "score": z,
                    "is_anomaly": flagged,
                    "severity": np.select(
                        [abs_z >= Z_HIGH, abs_z >= Z_MEDIUM, abs_z >= Z_LOW],
                        ["high", "medium", "low"],
                        default="",
                    ),
                    "direction": np.where(
                        flagged, np.where(z > 0, "spike", "drop"), ""
                    ),
                }
            )
        )

    if not frames:
       empty = pd.DataFrame(columns=OUTPUT_COLUMNS)
       empty["is_anomaly"] = empty["is_anomaly"].astype(bool)
       return empty, skipped

    return pd.concat(frames, ignore_index=True)[OUTPUT_COLUMNS], skipped


def main(argv=None):

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="output/sales_anomalies.csv")
    parser.add_argument("--no-fill-zero", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)

    scores, skipped = detect(
        pd.read_csv(args.input), fill_missing_as_zero=not args.no_fill_zero
    )

    anomalies = scores[scores["is_anomaly"].astype(bool)]

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    anomalies.to_csv(args.output, index=False)

    print(
        f"series skipped (under {MIN_SERIES_DAYS} days): {len(skipped)}  "
        f"days scored: {int(scores['score'].notna().sum())}  "
        f"anomalies: {len(anomalies)}"
    )
    if len(anomalies):
       print(anomalies["severity"].value_counts().to_string())
    print(f"written: {args.output}")


if __name__ == "__main__":
    main()