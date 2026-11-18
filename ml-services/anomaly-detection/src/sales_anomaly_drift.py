"""
Data drift check for the sales anomaly detector (R15-K6).

The thresholds were set up on one window of data (the clean seed today, the
first clean months of client data later). When a new load looks different
from that window, the detector's false-alarm rate and recall are no longer
what was measured, so we compare the two and warn.

Two columns are compared with an Evidently data drift report:

    quantity        units sold per product, warehouse and day
    zero_sales_day  whether that day had no sales (0) or some

A day counts when the warehouse reported it (a product with no row on a
reported day is a zero-sales day, a whole-warehouse feed gap is not a day).
This is the same rule the detector uses, because the days come from detect().

Drift never stops the batch job: callers log the warning and carry on.
"""

from dataclasses import dataclass, field
import logging
import re

import numpy as np
import pandas as pd

from .config import (
    DRIFT_ALERT_SHARE,
    DRIFT_CAT_THRESHOLD,
    DRIFT_LATEST_DAYS,
    DRIFT_NUM_THRESHOLD,
    DRIFT_SAMPLE_ROWS,
)


log = logging.getLogger("sales_anomaly_drift")

COLUMNS = ("quantity", "zero_sales_day")

# Distance measures, normalised: the score is a distance, so a HIGHER threshold
# means fewer alerts on every file size.
NUM_METHOD = "wasserstein"
CAT_METHOD = "jensenshannon"

_VALUE_DRIFT_TEST = "Value Drift for column "
_VALUE_DRIFT_METRIC = re.compile(r"^ValueDrift\(column=(?P<column>[^,]+),")


@dataclass
class DriftResult:
    """Outcome of one drift check. `alert` is the only thing the job acts on."""

    alert: bool
    drift_share: float
    columns: dict
    reference_rows: int
    latest_rows: int
    reference_zero_share: float
    latest_zero_share: float
    reference_mean_quantity: float
    latest_mean_quantity: float
    html: str = field(default="", repr=False)

    def metrics(self):
        """Numbers worth logging to MLflow."""

        values = {
            "drift_share": self.drift_share,
            "drift_alert": float(self.alert),
            "drift_reference_rows": float(self.reference_rows),
            "drift_latest_rows": float(self.latest_rows),
            "zero_share_reference": self.reference_zero_share,
            "zero_share_latest": self.latest_zero_share,
            "mean_quantity_reference": self.reference_mean_quantity,
            "mean_quantity_latest": self.latest_mean_quantity,
        }

        for name, info in self.columns.items():
            if info["score"] is not None:
                values[f"drift_score_{name}"] = info["score"]

        return values

    def message(self):
        """One line for the log."""

        drifted = [name for name, info in self.columns.items() if info["drift"]]

        return (
            f"{len(drifted)} of {len(self.columns)} columns drifted"
            f" ({', '.join(drifted) if drifted else 'none'}); "
            f"zero-sales days {100 * self.reference_zero_share:.1f}% in the setup "
            f"window vs {100 * self.latest_zero_share:.1f}% in the latest load; "
            f"mean quantity {self.reference_mean_quantity:.1f} vs "
            f"{self.latest_mean_quantity:.1f}"
        )


def known_days(scores):
    """Rows of detect() output that have a quantity (feed-gap days do not)."""

    return scores[scores["quantity"].notna()]


def latest_window(scores, days=DRIFT_LATEST_DAYS):
    """The last `days` calendar days of a detect() output."""

    if scores.empty:
        return scores

    cutoff = scores["date"].max() - pd.Timedelta(days=days - 1)

    return scores[scores["date"] >= cutoff]


def drift_frame(scores, max_rows=DRIFT_SAMPLE_ROWS):
    """The two columns Evidently compares, from a detect() output."""

    days = known_days(scores)

    if days.empty:
        raise ValueError("No days with sales data to compare.")

    quantity = days["quantity"].astype(float).to_numpy()

    frame = pd.DataFrame(
        {
            "quantity": quantity,
            "zero_sales_day": np.where(quantity == 0, "zero", "sold"),
        }
    )

    if len(frame) > max_rows:
        frame = frame.sample(max_rows, random_state=0)

    return frame.reset_index(drop=True)


def _stats(scores):

    days = known_days(scores)
    quantity = days["quantity"].astype(float)

    return len(days), float((quantity == 0).mean()), float(quantity.mean())


def check_drift(
    reference_scores,
    latest_scores,
    num_threshold=DRIFT_NUM_THRESHOLD,
    cat_threshold=DRIFT_CAT_THRESHOLD,
    alert_share=DRIFT_ALERT_SHARE,
):
    """
    Compare the setup window with the latest load (both detect() outputs).

    Raises ValueError when either side has no days with data. Evidently errors
    pass through; the caller decides what to do with them.
    """

    from evidently import DataDefinition, Dataset, Report
    from evidently.presets import DataDriftPreset

    reference = drift_frame(reference_scores)
    latest = drift_frame(latest_scores)

    definition = DataDefinition(
        numerical_columns=["quantity"], categorical_columns=["zero_sales_day"]
    )

    report = Report(
        [
            DataDriftPreset(
                columns=list(COLUMNS),
                # Fixed methods, so the threshold means the same on any file
                # size. Left unset, Evidently switches to a p-value test for
                # references of 1,000 rows or fewer, and then a higher
                # threshold makes an alert MORE likely.
                num_method=NUM_METHOD,
                cat_method=CAT_METHOD,
                num_threshold=num_threshold,
                cat_threshold=cat_threshold,
                drift_share=alert_share,
            )
        ],
        include_tests=True,
    )

    snapshot = report.run(
        current_data=Dataset.from_pandas(latest, data_definition=definition),
        reference_data=Dataset.from_pandas(reference, data_definition=definition),
    )

    summary = snapshot.dict()
    columns = {}

    for test in summary.get("tests", []):
        name = str(test.get("name", ""))

        if name.startswith(_VALUE_DRIFT_TEST):
            status = test.get("status")
            status = getattr(status, "value", status)
            columns[name[len(_VALUE_DRIFT_TEST):]] = {
                "drift": str(status).upper() == "FAIL",
                "score": None,
            }

    for metric in summary.get("metrics", []):
        match = _VALUE_DRIFT_METRIC.match(str(metric.get("metric_name", "")))

        if match and match.group("column") in columns:
            columns[match.group("column")]["score"] = float(metric["value"])

    if set(columns) != set(COLUMNS):
        raise RuntimeError(
            f"Evidently did not return a drift result for {COLUMNS}; got "
            f"{sorted(columns)}. Check the installed evidently version (0.7.x)."
        )

    drift_share = sum(info["drift"] for info in columns.values()) / len(columns)

    reference_rows, reference_zero, reference_mean = _stats(reference_scores)
    latest_rows, latest_zero, latest_mean = _stats(latest_scores)

    return DriftResult(
        alert=drift_share >= alert_share,
        drift_share=drift_share,
        columns=columns,
        reference_rows=reference_rows,
        latest_rows=latest_rows,
        reference_zero_share=reference_zero,
        latest_zero_share=latest_zero,
        reference_mean_quantity=reference_mean,
        latest_mean_quantity=latest_mean,
        html=snapshot.get_html_str(as_iframe=False),
    )