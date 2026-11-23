"""
Sales anomaly detection: unusual spikes and drops per product and warehouse.

Input: sales history with columns sale_date, sku_id (or product_code),
warehouse_id (or warehouse_code, warehouse), quantity_sold. One daily series
per product and warehouse (rows for the same day are summed).

Method: seasonal-naive baseline + robust z-score (see README).

    expected(t) = median of the same weekday over the previous 8 weeks
                  (values at t-7, t-14, ..., t-56; at least 4 needed)
    rate(t)     = max(expected, mean of those values, 1)
    scale(t)    = max(1.4826 * MAD of those values,
                      sqrt(rate + rate^2 / DISPERSION_K), 1)
    z(t)        = (quantity(t) - expected(t)) / scale(t)

Spikes are flagged by z (z >= Z_SPIKE). Drops are flagged by share of the
expected value (see classify), because under over-dispersed sales a fall to
zero is only a few scale units and z cannot separate it from spike noise.

Only strictly earlier days are used: a day's score never depends on that
day's future. Thresholds live in src/config.py; Z_SPIKE is calibrated on the
clean seed (see src/calibrate_sales_anomaly.py).

Run (from ml-services/anomaly-detection):
    python -m src.sales_anomaly --input <sales.csv> --output output/sales_anomalies.csv
"""

import argparse
import logging
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from .config import (
    DISPERSION_K,
    DROP_HIGH,
    DROP_LOW,
    DROP_MEDIUM,
    DROP_MIN_EXPECTED,
    LOOKBACK_WEEKS,
    MAD_TO_SIGMA,
    MIN_SERIES_DAYS,
    MIN_WEEKS,
    RUN_GAP_DAYS,
    SPIKE_HIGH,
    SPIKE_MEDIUM,
    Z_SPIKE,
)

log = logging.getLogger(__name__)

COLUMN_ALIASES = {
    "date": ("sale_date", "date"),
    # Canonical columns first: staging rows from #323 carry both the client
    # code and the canonical ID, and #327 must publish the canonical one.
    "product": ("sku_id", "product_code", "sku"),
    "warehouse": ("warehouse_id", "warehouse_code", "warehouse"),
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
    "run_start",
    "reason",
]


def normalize_columns(df):
    """Return a frame with columns date, product, warehouse, quantity."""

    picked = {}

    for name, aliases in COLUMN_ALIASES.items():
        found = next((a for a in aliases if a in df.columns), None)

        if found is None:
            raise ValueError(
                f"No {name} column. Expected one of {aliases}; got {list(df.columns)}."
            )

        picked[name] = found

    out = pd.DataFrame(
        {
            # ISO dates (YYYY-MM-DD, as in the #322 spec); anything else is a bad row.
            "date": pd.to_datetime(
                df[picked["date"]], format="ISO8601", errors="coerce"
            ),
            "product": df[picked["product"]].astype("string").str.strip(),
            "warehouse": df[picked["warehouse"]].astype("string").str.strip(),
            "quantity": pd.to_numeric(df[picked["quantity"]], errors="coerce"),
        }
    )

    blank_key = (
        out["product"].isna()
        | out["product"].eq("")
        | out["warehouse"].isna()
        | out["warehouse"].eq("")
    ).fillna(True)
    # np.isfinite also catches NaN and "inf"/"Infinity", which pd.to_numeric
    # accepts; one inf would make the noise scale infinite for 8 weeks.
    finite = np.isfinite(out["quantity"].astype(float))
    bad = out["date"].isna() | ~finite | blank_key | (out["quantity"] < 0)

    if bad.any():
        log.warning(
            "Dropping %d rows with an invalid date, quantity, product or warehouse.",
            int(bad.sum()),
        )
        out = out[~bad].copy()

    out["date"] = out["date"].dt.normalize()

    return out


def classify(quantity, expected, z, z_spike=None):
    """Return (direction, severity) arrays; empty strings where not an anomaly."""

    quantity = np.asarray(quantity, dtype=float)
    expected = np.asarray(expected, dtype=float)
    z = np.asarray(z, dtype=float)
    scored = np.isfinite(z)
    z_spike = Z_SPIKE if z_spike is None else z_spike

    if np.isfinite(z_spike) and not z_spike < SPIKE_MEDIUM < SPIKE_HIGH:
        raise ValueError(
            f"z_spike {z_spike} must be below SPIKE_MEDIUM ({SPIKE_MEDIUM}) and "
            f"SPIKE_HIGH ({SPIKE_HIGH}); raise those thresholds first, or no "
            "spike would ever be low."
        )

    spike = scored & (z >= z_spike)
    drop = (
        scored
        & ~spike
        & (expected >= DROP_MIN_EXPECTED)
        & (quantity <= DROP_LOW * expected)
    )

    direction = np.where(spike, "spike", np.where(drop, "drop", ""))
    severity = np.select(
        [
            spike & (z >= SPIKE_HIGH),
            spike & (z >= SPIKE_MEDIUM),
            spike,
            drop & (quantity <= DROP_HIGH * expected),
            drop & (quantity <= DROP_MEDIUM * expected),
            drop,
        ],
        ["high", "medium", "low", "high", "medium", "low"],
        default="",
    )

    return direction, severity


def explain(quantity, expected, z, direction, weeks):
    """Return a short reason per day; empty string where not an anomaly."""

    reasons = []

    for q, e, score, d, w in zip(quantity, expected, z, direction, weeks):
        basis = f"same weekday median of the last {int(w)} weeks"

        if d == "spike":
            reasons.append(f"sold {q:.0f} vs expected {e:.0f} (z {score:.1f}, {basis})")
        elif d == "drop":
            reasons.append(
                f"sold {q:.0f} vs expected {e:.0f} ({100 * q / e:.0f}% of the {basis})"
            )
        else:
            reasons.append("")

    return np.array(reasons, dtype=object)


def run_starts(direction, max_gap_days=RUN_GAP_DAYS):
    """
    True on the first day of each incident.

    A flagged day continues the incident when it has the same direction as
    the last flagged day and comes at most max_gap_days after it, so a
    feed-gap day or a weekday under DROP_MIN_EXPECTED does not split one
    incident into several events. Positions are days: the series is daily.
    """

    direction = np.asarray(direction)
    starts = np.zeros(len(direction), dtype=bool)
    flagged = np.flatnonzero(direction != "")

    if len(flagged):
        new = np.ones(len(flagged), dtype=bool)
        new[1:] = (direction[flagged[1:]] != direction[flagged[:-1]]) | (
            np.diff(flagged) > max_gap_days
        )
        starts[flagged] = new

    return starts


def _score_series(values):
    """Return (expected, scale, z, weeks) where weeks is the history used per day."""

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
        mean = np.nanmean(lagged, axis=1)

    # The mean keeps the scale honest when the median is 0 (slow sellers).
    rate = np.maximum(np.maximum(expected, mean), 1.0)
    noise = np.sqrt(rate + rate**2 / DISPERSION_K)
    scale = np.maximum.reduce([MAD_TO_SIGMA * mad, noise, np.ones(n)])

    z = (v - expected) / scale
    z[count < MIN_WEEKS] = np.nan

    return expected, scale, z, count


def score_series(values):
    """
    Return (expected, scale, z) for a daily series (arrays of length n).

    z is NaN for days with fewer than MIN_WEEKS same-weekday values of
    history, and for days with no value (a feed gap). Uses only values
    strictly before each day.
    """

    expected, scale, z, _ = _score_series(values)

    return expected, scale, z


def detect(df, fill_missing_as_zero=True, z_spike=None):
    """
    Score every product/warehouse series.

    Returns (scores, skipped). scores has one row per scored day (see
    OUTPUT_COLUMNS). skipped lists (product, warehouse, days) for series
    with fewer than MIN_SERIES_DAYS days of data; each gets a log line and
    no flags. z_spike overrides Z_SPIKE for this call only.

    A missing day counts as 0 sales only when the warehouse reported other
    products that day; a day the whole warehouse is missing is left unscored.

    run_start marks the first day of each incident: same-direction anomalies
    at most RUN_GAP_DAYS apart are one incident (a SKU that stops selling, a
    3-day promotion), so downstream jobs publish one event per incident.
    """

    data = normalize_columns(df)

    # Days on which each warehouse sent at least one row. A day the whole
    # warehouse is missing is a feed gap, not zero sales: it stays unscored.
    # This also covers a warehouse whose feed is a day behind at the end.
    warehouse_days = {
        warehouse: pd.DatetimeIndex(days)
        for warehouse, days in data.groupby("warehouse")["date"].unique().items()
    }

    frames = []
    skipped = []

    for (product, warehouse), group in data.groupby(
        ["product", "warehouse"], sort=True
    ):
        days_of_data = group["date"].nunique()

        if days_of_data < MIN_SERIES_DAYS:
            log.warning(
                "Skipping %s / %s: %d days of data, need at least %d (8 weeks).",
                product,
                warehouse,
                days_of_data,
                MIN_SERIES_DAYS,
            )
            skipped.append((product, warehouse, days_of_data))
            continue

        reported = warehouse_days[warehouse]
        daily = group.groupby("date")["quantity"].sum()
        calendar = pd.date_range(daily.index.min(), reported.max(), freq="D")
        daily = daily.reindex(calendar)

        if fill_missing_as_zero:
            # Zero only where the warehouse reported that day but this product
            # has no row. Feed-gap days stay NaN, so they are not scored and
            # do not enter the same-weekday baseline.
            no_sale = daily.isna().to_numpy() & calendar.isin(reported)
            daily.iloc[no_sale] = 0.0

        quantity = daily.to_numpy()
        expected, scale, z, weeks = _score_series(quantity)
        direction, severity = classify(quantity, expected, z, z_spike)

        is_anomaly = direction != ""
        run_start = run_starts(direction)
        reason = explain(quantity, expected, z, direction, weeks)

        frames.append(
            pd.DataFrame(
                {
                    "product": product,
                    "warehouse": warehouse,
                    "date": daily.index,
                    "quantity": quantity,
                    "expected": expected,
                    "scale": scale,
                    "score": z,
                    "is_anomaly": is_anomaly,
                    "severity": severity,
                    "direction": direction,
                    "run_start": run_start,
                    "reason": reason,
                }
            )
        )

    if not frames:
        empty = pd.DataFrame(columns=OUTPUT_COLUMNS)
        empty["is_anomaly"] = empty["is_anomaly"].astype(bool)
        empty["run_start"] = empty["run_start"].astype(bool)
        return empty, skipped

    return pd.concat(frames, ignore_index=True)[OUTPUT_COLUMNS], skipped


def main(argv=None):

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="output/sales_anomalies.csv")
    parser.add_argument("--no-fill-zero", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)

    # Read as text so product codes keep their leading zeros.
    scores, skipped = detect(
        pd.read_csv(args.input, dtype=str),
        fill_missing_as_zero=not args.no_fill_zero,
    )

    anomalies = scores[scores["is_anomaly"].astype(bool)]

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    anomalies.to_csv(args.output, index=False)

    print(
        f"series skipped (under {MIN_SERIES_DAYS} days): {len(skipped)}  "
        f"days scored: {int(scores['score'].notna().sum())}  "
        f"anomalies: {len(anomalies)}  "
        f"incidents (run starts): {int(anomalies['run_start'].sum())}"
    )
    if len(anomalies):
        print(anomalies.groupby(["direction", "severity"]).size().to_string())
    print(f"written: {args.output}")


if __name__ == "__main__":
    main()
