"""
Train the R15 production forecast on the seed, compare it with seasonal naive,
register it in MLflow with Ajith's signature and promote it to Production.

Run from ml-services/demand-forecast/prophet with MLflow up:
    MLFLOW_TRACKING_URI=http://localhost:5000 python -m src.register_production_model
Exit code 1 (registered, not promoted) if the model does not beat naive.
"""

import hashlib
import json
from datetime import datetime, timezone

import mlflow
import numpy as np
import pandas as pd
from mlflow.models import ModelSignature
from mlflow.tracking import MlflowClient
from mlflow.types import ColSpec, Schema
from prophet.serialize import model_to_json

from src.forecast_pyfunc import DemandForecastModel, aggregate_forecast, fit_prophet, horizon_bucket
from src.multi_horizon_config import (
    HOLDOUT_DAYS,
    HORIZON_BUCKETS,
    MIN_CALIBRATION_PREDICTION,
    MLFLOW_EXPERIMENT,
    PROJECT_ROOT,
    RANDOM_SEED,
    REGISTERED_MODEL_NAME,
    REGISTRY_DIR,
    REPO_ROOT,
    SEED_SALES_PATH,
    SHARE_WINDOW_DAYS,
)
from src.seed_demand import aggregate_daily, load_seed_sales, pair_shares

# Matches contracts/openapi/forecast.yaml and production_model.py.
SIGNATURE = ModelSignature(
    inputs=Schema([
        ColSpec("string", "sku_id"),
        ColSpec("string", "warehouse_id"),
        ColSpec("long", "horizon"),
    ]),
    outputs=Schema([
        ColSpec("string", "date"),
        ColSpec("double", "predicted"),
        ColSpec("double", "lower_bound"),
        ColSpec("double", "upper_bound"),
    ]),
)


def wape(actual: pd.Series, predicted: pd.Series) -> float:
    total = actual.sum()
    return float(np.abs(actual - predicted).sum() / total) if total > 0 else float("nan")


def holdout_frame(sales: pd.DataFrame) -> tuple[pd.DataFrame, pd.Timestamp]:
    """Pair-level actuals for the last HOLDOUT_DAYS with model and naive predictions."""
    cutoff = sales["date"].max() - pd.Timedelta(days=HOLDOUT_DAYS)
    train = sales[sales["date"] <= cutoff]
    test = sales[sales["date"] > cutoff].copy()

    model = fit_prophet(aggregate_daily(train))
    aggregate = aggregate_forecast(model, cutoff + pd.Timedelta(days=1), HOLDOUT_DAYS)
    shares = pd.Series(pair_shares(train, end=cutoff))

    test["key"] = test["sku_id"] + "|" + test["warehouse_id"]
    test["day"] = (test["date"] - cutoff).dt.days
    test = test.merge(aggregate, on="date", how="left")
    test["predicted"] = test["yhat"] * test["key"].map(shares).fillna(0.0)

    # Seasonal naive (weekly): repeat each pair's last 7 days before the cutoff.
    last_week = train[train["date"] > cutoff - pd.Timedelta(days=7)].copy()
    last_week["key"] = last_week["sku_id"] + "|" + last_week["warehouse_id"]
    last_week["lag_day"] = (cutoff - last_week["date"]).dt.days
    naive = last_week.set_index(["key", "lag_day"])["quantity_sold"]
    lag_day = 6 - (test["day"] - 1) % 7
    test["naive"] = naive.reindex(pd.MultiIndex.from_arrays([test["key"], lag_day])).fillna(0.0).to_numpy()

    test["bucket"] = test["day"].map(horizon_bucket)
    return test, cutoff


def evaluate(holdout: pd.DataFrame) -> dict[str, float]:
    metrics = {
        "wape_model_all": wape(holdout["quantity_sold"], holdout["predicted"]),
        "wape_naive_all": wape(holdout["quantity_sold"], holdout["naive"]),
    }
    for bucket, group in holdout.groupby("bucket"):
        tag = bucket.replace("-", "_")
        metrics[f"wape_model_{tag}"] = wape(group["quantity_sold"], group["predicted"])
        metrics[f"wape_naive_{tag}"] = wape(group["quantity_sold"], group["naive"])
    return metrics


def calibrate_intervals(holdout: pd.DataFrame) -> tuple[dict, dict]:
    """80% ratio interval per bucket from half the pairs, coverage checked on the other half."""
    rng = np.random.default_rng(RANDOM_SEED)
    keys = holdout["key"].unique()
    calibration_keys = set(rng.choice(keys, size=len(keys) // 2, replace=False))

    usable = holdout[holdout["predicted"] >= MIN_CALIBRATION_PREDICTION].copy()
    usable["ratio"] = usable["quantity_sold"] / usable["predicted"] - 1
    calibration = usable[usable["key"].isin(calibration_keys)]
    check = usable[~usable["key"].isin(calibration_keys)]

    intervals, coverage = {}, {}
    for bucket, group in calibration.groupby("bucket"):
        low, high = group["ratio"].quantile([0.10, 0.90])
        intervals[bucket] = {"low": float(low), "high": float(high), "observations": int(len(group))}
        held = check[check["bucket"] == bucket]
        coverage[bucket] = float(((held["ratio"] >= low) & (held["ratio"] <= high)).mean())
    return intervals, coverage


def model_card(sales, digest, cutoff, metrics, intervals, coverage, pairs) -> str:
    lines = [
        f"# {REGISTERED_MODEL_NAME}: R15 production demand forecast",
        "",
        f"- Trained: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC",
        f"- Data: `{SEED_SALES_PATH.relative_to(REPO_ROOT).as_posix()}` sha256 `{digest}`, "
        f"{len(sales)} rows, {sales['date'].min().date()} to {sales['date'].max().date()}, {pairs} SKU/warehouse pairs",
        "- Method: Prophet on total daily demand (US holidays regressor), split to pairs by "
        f"their share of the last {SHARE_WINDOW_DAYS} days; 80% interval from pooled pair-level errors",
        f"- Holdout: last {HOLDOUT_DAYS} days after {cutoff.date()} (time-based, no shuffling)",
        "- Input: sku_id (SKU-NNNNNN), warehouse_id (WH-XXX-NN), horizon 1-90",
        "- Output: horizon rows of date, predicted, lower_bound (p10), upper_bound (p90), from tomorrow UTC",
        "",
        "| Horizon (days) | WAPE model | WAPE seasonal naive | 80% coverage (held-out pairs) | Calibration obs |",
        "|---|---|---|---|---|",
    ]
    for bucket in intervals:
        tag = bucket.replace("-", "_")
        lines.append(
            f"| {bucket} | {metrics[f'wape_model_{tag}']:.3f} | {metrics[f'wape_naive_{tag}']:.3f} "
            f"| {coverage[bucket]:.2f} | {intervals[bucket]['observations']} |"
        )
    lines.append(
        f"| all | {metrics['wape_model_all']:.3f} | {metrics['wape_naive_all']:.3f} | | |"
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    sales = load_seed_sales()
    digest = hashlib.sha256(SEED_SALES_PATH.read_bytes()).hexdigest()[:12]

    holdout, cutoff = holdout_frame(sales)
    metrics = evaluate(holdout)
    intervals, coverage = calibrate_intervals(holdout)
    missing = {
        f"{low}-{high}" for low, high in HORIZON_BUCKETS
    } - intervals.keys()

    if missing:
        raise SystemExit(
            f"No calibration data for horizon buckets: {sorted(missing)}"
        )
    metrics.update({f"coverage_80_{b.replace('-', '_')}": c for b, c in coverage.items()})

    # Final model on all history.
    prophet = fit_prophet(aggregate_daily(sales))
    shares = pair_shares(sales)

    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "prophet": REGISTRY_DIR / "prophet_seed.json",
        "shares": REGISTRY_DIR / "pair_shares.json",
        "intervals": REGISTRY_DIR / "pair_intervals.json",
    }
    artifacts["prophet"].write_text(model_to_json(prophet), encoding="utf-8")
    artifacts["shares"].write_text(json.dumps(shares), encoding="utf-8")
    artifacts["intervals"].write_text(json.dumps(intervals, indent=2), encoding="utf-8")

    card = model_card(sales, digest, cutoff, metrics, intervals, coverage, len(shares))
    card_path = REGISTRY_DIR / "MODEL_CARD.md"
    card_path.write_text(card, encoding="utf-8")
    holdout_path = REGISTRY_DIR / "holdout_predictions.csv"
    holdout[["date", "sku_id", "warehouse_id", "day", "quantity_sold", "predicted", "naive"]].to_csv(holdout_path, index=False)

    example_sku, example_wh = next(iter(shares)).split("|")

    mlflow.set_experiment(MLFLOW_EXPERIMENT)
    with mlflow.start_run(run_name="r15_seed_production") as run:
        mlflow.log_params({
            "data_path": SEED_SALES_PATH.relative_to(REPO_ROOT).as_posix(),
            "data_sha256": digest,
            "rows": len(sales),
            "pairs": len(shares),
            "date_start": str(sales["date"].min().date()),
            "date_end": str(sales["date"].max().date()),
            "holdout_cutoff": str(cutoff.date()),
            "holdout_days": HOLDOUT_DAYS,
            "share_window_days": SHARE_WINDOW_DAYS,
            "method": "prophet_top_down_pair_share",
        })
        mlflow.log_metrics(metrics)
        mlflow.log_artifact(str(card_path))
        mlflow.log_artifact(str(holdout_path))
        info = mlflow.pyfunc.log_model(
            name="model",
            python_model=DemandForecastModel(),
            artifacts={name: str(path) for name, path in artifacts.items()},
            signature=SIGNATURE,
            input_example=pd.DataFrame([{"sku_id": example_sku, "warehouse_id": example_wh, "horizon": 3}]),
            code_paths=[str(PROJECT_ROOT / "src")],
        )

    client = MlflowClient()
    registered = mlflow.register_model(info.model_uri, REGISTERED_MODEL_NAME)
    client.update_model_version(REGISTERED_MODEL_NAME, registered.version, description=card)
    print(card)
    print(f"MLflow run {run.info.run_id}, registered {REGISTERED_MODEL_NAME} version {registered.version}")

    if not metrics["wape_model_all"] <= metrics["wape_naive_all"]:
        print("Model does not beat seasonal naive on the holdout. Registered but NOT promoted.")
        raise SystemExit(1)

    client.transition_model_version_stage(
        REGISTERED_MODEL_NAME,
        registered.version,
        stage="Production",
        archive_existing_versions=True,
    )
    print(f"Promoted {REGISTERED_MODEL_NAME}/{registered.version} to Production.")


if __name__ == "__main__":
    main()