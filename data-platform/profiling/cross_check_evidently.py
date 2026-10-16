from pathlib import Path

import logging
import pandas as pd
import numpy as np
from evidently import Report
from evidently.presets import DataDriftPreset

from src.profiler import Profiler

RESULTS_DIR = Path(__file__).resolve().parent / "results"   # tracked, unlike reports/
VALUE_DRIFT_PREFIX = "Value Drift for column "

# Configure standard logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def create_datasets():
    """Generate a baseline dataset, an identical one, and a drifted one."""
    rng = np.random.default_rng(42)
    rows = 10_000

    baseline = pd.DataFrame({
        "sku_id": rng.choice([f"SKU{i:03d}" for i in range(1, 10)], size=rows),
        "warehouse_id": rng.choice(["WH1", "WH2", "WH3"], size=rows, p=[0.5, 0.3, 0.2]),
        "quantity_sold": rng.normal(loc=50, scale=10, size=rows),
        "unit_price": rng.normal(loc=100, scale=20, size=rows),
    })

    # No Drift: Exact identical copy
    no_drift = baseline.copy()

    # Drifted: Inject specific shifts
    drifted = baseline.copy()

    # 1. Mean shift > 1 std (Custom catches this, Evidently catches this)
    drifted["unit_price"] = rng.normal(loc=130, scale=20, size=rows)

    # 2. Distribution shape change without mean shift (Custom misses this, Evidently catches this)
    # Baseline mean is ~50. New mean is ~50, but variance is drastically wider.
    drifted["quantity_sold"] = rng.normal(loc=50, scale=40, size=rows)

    # 3. Minor proportion shift (Custom triggers at 10% absolute diff)
    drifted["warehouse_id"] = rng.choice(["WH1", "WH2", "WH3"], size=rows, p=[0.35, 0.45, 0.2])

    # 4. Null injection (Custom explicitly checks this)
    null_idx = rng.choice(rows, size=int(rows * 0.12), replace=False)
    drifted.loc[null_idx, "sku_id"] = np.nan

    return baseline, no_drift, drifted


def run_custom_drift(old_df, new_df):
    profiler = Profiler()
    return profiler.compare(old_df, new_df)


def run_evidently_drift(old_df, new_df, html_path=None):
    report = Report(metrics=[DataDriftPreset()], include_tests=True)
    snapshot = report.run(reference_data=old_df, current_data=new_df)
    if html_path is not None:
        Path(html_path).parent.mkdir(parents=True, exist_ok=True)
        snapshot.save_html(str(html_path))
    return snapshot.dict()

def summarize_evidently(evidently_report: dict) -> dict:
    """Extract dataset-level and per-column drift from Evidently 0.7.x output."""
    summary = {"dataset_drift": None, "drifted_count": None,
               "drift_share": None, "columns": {}}

    for metric in evidently_report.get("metrics", []):
        name = str(metric.get("metric_name", ""))
        value = metric.get("value")
        if name.startswith("DriftedColumnsCount") and isinstance(value, dict):
            summary["drifted_count"] = value["count"]
            summary["drift_share"] = value["share"]
            summary["dataset_drift"] = value["share"] >= 0.5   # Evidently default drift_share

    for test in evidently_report.get("tests", []):
        test_name = str(test.get("name", ""))
        if test_name.startswith(VALUE_DRIFT_PREFIX):
            status = test.get("status")
            status = getattr(status, "value", status)          # enum -> string
            summary["columns"][test_name[len(VALUE_DRIFT_PREFIX):]] = {
                "drift": str(status).upper() == "FAIL",
                "detail": test.get("description", ""),         # method, score, threshold
            }

    if summary["dataset_drift"] is None:
        raise RuntimeError(
            "DriftedColumnsCount not found in Evidently output. "
            "Check the installed evidently version (expects 0.7.x)."
        )
    return summary




def _make_sales(rng, rows):
    return pd.DataFrame({
        "sku_id": rng.choice([f"SKU{i:03d}" for i in range(1, 10)], size=rows),
        "warehouse_id": rng.choice(["WH1", "WH2", "WH3"], size=rows, p=[0.5, 0.3, 0.2]),
        "quantity_sold": rng.normal(loc=50, scale=10, size=rows),
        "unit_price": rng.normal(loc=100, scale=20, size=rows),
    })


def create_datasets(rows=10_000):
    baseline = _make_sales(np.random.default_rng(42), rows)
    no_drift = _make_sales(np.random.default_rng(7), rows)    # same distribution, new sample

    rng = np.random.default_rng(99)
    drifted = _make_sales(rng, rows)
    drifted["unit_price"] = rng.normal(loc=130, scale=20, size=rows)        # mean shift
    drifted["quantity_sold"] = rng.normal(loc=50, scale=40, size=rows)      # variance only
    drifted["warehouse_id"] = rng.choice(["WH1", "WH2", "WH3"], size=rows, p=[0.35, 0.45, 0.2])
    null_idx = rng.choice(rows, size=int(rows * 0.12), replace=False)
    drifted.loc[null_idx, "sku_id"] = np.nan                                # null injection
    return baseline, no_drift, drifted

def build_comparison(custom_report: dict, ev: dict) -> pd.DataFrame:
    rows = []
    for col in sorted(ev["columns"]):
        custom = custom_report["column_drift"].get(col, {})
        custom_drift = custom.get("status", "no_drift") != "no_drift"
        ev_drift = ev["columns"][col]["drift"]
        rows.append({
            "column": col,
            "custom": "drift" if custom_drift else "no drift",
            "evidently": "drift" if ev_drift else "no drift",
            "agree": custom_drift == ev_drift,
            "custom_reasons": "; ".join(custom.get("reasons", [])),
            "evidently_detail": ev["columns"][col]["detail"],
        })
    return pd.DataFrame(rows)


def main():
    baseline, no_drift, drifted = create_datasets()
    RESULTS_DIR.mkdir(exist_ok=True)

    for scenario, current in [("no_drift", no_drift), ("deliberate_drift", drifted)]:
        custom = run_custom_drift(baseline, current)
        ev = summarize_evidently(run_evidently_drift(
            baseline, current, html_path=RESULTS_DIR / f"evidently_{scenario}.html"))
        table = build_comparison(custom, ev)
        table.to_csv(RESULTS_DIR / f"evidently_comparison_{scenario}.csv", index=False)
        print(f"\n=== {scenario} | custom: {custom['status']} | "
              f"evidently dataset drift: {ev['dataset_drift']} ({ev['drift_share']:.0%}) ===")
        print(table.to_string(index=False))

if __name__ == "__main__":
    main()