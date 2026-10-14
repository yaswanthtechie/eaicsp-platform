import logging
import pandas as pd
import numpy as np
from evidently import Report
from evidently.presets import DataDriftPreset

from src.profiler import Profiler

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


def run_evidently_drift(old_df, new_df):
    report = Report(metrics=[DataDriftPreset()])

    snapshot = report.run(
        reference_data=old_df,
        current_data=new_df,
    )

    snapshot.save_html("reports/evidently_drift_report.html")
    return snapshot.dict()


def log_comparison(scenario_name, custom_report, evidently_report):
    logger.info("=" * 50)
    logger.info(f"SCENARIO: {scenario_name}")
    logger.info("=" * 50)

    # Custom profiler summary
    logger.info(f"[Custom] Overall Status: {custom_report.get('status')}")

    for col, details in custom_report.get("column_drift", {}).items():
        if details.get("status") != "no_drift":
            reasons = ", ".join(details.get("reasons", []))
            logger.info(
                f"  - [Custom] {col}: "
                f"{details.get('status')} ({reasons})"
            )

    # Evidently 0.7.x summary
    metrics = evidently_report.get("metrics", [])
    drifted_columns = []
    column_count = None
    drift_share = None

    for metric in metrics:
        value = metric.get("value", {})
        if not isinstance(value, dict):
            continue

        metric_id = str(metric.get("metric_id", ""))

        # Dataset-level drift summary
        if "DriftedColumnsCount" in metric_id:
            column_count = value.get("count")
            drift_share = value.get("share")

        # Individual column drift results
        if value.get("drift_detected") is True:
            column = value.get("column", metric_id)
            test = value.get("stattest_name", "unknown")
            score = value.get("drift_score")

            drifted_columns.append(column)

            score_text = (
                f"{score:.4f}"
                if isinstance(score, (int, float))
                else str(score)
            )

            logger.info(
                f"  - [Evidently] {column}: Drifted "
                f"(Test: {test}, Score: {score_text})"
            )

    logger.info(f"[Evidently] Drifted Columns: {len(drifted_columns)}")

    if drift_share is not None:
        logger.info(f"[Evidently] Drift Share: {drift_share:.2%}")

    if column_count is not None:
        logger.info(f"[Evidently] Columns Evaluated: {column_count}")

    if drift_share is not None:
        logger.info(
            f"[Evidently] Dataset Drift Detected: {drift_share >= 0.5}"
        )
    else:
        logger.warning(
            "[Evidently] Could not extract dataset drift status "
            "from the expected metric structure."
        )
        logger.warning("[Evidently] Available metric IDs:")
        for metric in metrics:
            logger.warning(f"  {metric.get('metric_id')}")


def main():
    logger.info("Creating evaluation datasets...")
    baseline, no_drift, drifted = create_datasets()

    logger.info("Executing Test 1: No Drift")
    custom_no_drift = run_custom_drift(baseline, no_drift)
    evidently_no_drift = run_evidently_drift(baseline, no_drift)
    log_comparison("NO DRIFT", custom_no_drift, evidently_no_drift)

    logger.info("Executing Test 2: Deliberate Drift")
    custom_drift = run_custom_drift(baseline, drifted)
    evidently_drift = run_evidently_drift(baseline, drifted)
    log_comparison("DELIBERATE DRIFT", custom_drift, evidently_drift)


if __name__ == "__main__":
    main()