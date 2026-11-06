"""Configuration for daily multi-horizon forecasting. No magic numbers elsewhere."""

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PROJECT_ROOT.parents[2]

DATA_PATH = PROJECT_ROOT / "data" / "m5_daily_sales.csv"

# R15 seed: one row per date x canonical SKU x canonical warehouse.
# Written by `make seed` (data-platform/out/sales_daily.csv).
SEED_SALES_PATH = Path(os.getenv(
    "SEED_SALES_PATH",
    REPO_ROOT / "data-platform" / "out" / "sales_daily.csv",
))
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"

MODEL_DIR = PROJECT_ROOT / "models" / "multi_horizon"
PROPHET_MODEL_PATH = MODEL_DIR / "prophet_daily.json"
XGB_MODEL_PATH = MODEL_DIR / "xgb_daily.pkl"
INTERVALS_PATH = MODEL_DIR / "horizon_intervals.json"
BACKTEST_RESULTS_PATH = MODEL_DIR / "backtest_results.csv"

WEIGHTS_PATH = PROJECT_ROOT / "models" / "promoted" / "ensemble_weights.json"

HORIZONS = {
    "1_day": 1,
    "7_day": 7,
    "30_day": 30,
    "90_day": 90,
}

MAX_FORECAST_DAYS = 90

RANDOM_SEED = 42

PROPHET_PARAMS = {
    "yearly_seasonality": True,
    "weekly_seasonality": True,
    "daily_seasonality": False,
}

PROPHET_COUNTRY_HOLIDAYS = "US"

XGB_PARAMS = {
    "n_estimators": 300,
    "learning_rate": 0.03,
    "max_depth": 5,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "objective": "reg:squarederror",
    "random_state": RANDOM_SEED,
}

# Rolling-origin backtest on the aggregate series:
# refit at each cutoff, forecast 90 days, score each horizon.
# 730 days of seed history: 365 min training + 90 horizon leaves 275 days,
# so 19 cutoffs every 14 days.
BACKTEST_CUTOFFS = 19
BACKTEST_STEP_DAYS = 14
CALIBRATION_CUTOFFS = 13
MIN_TRAINING_DAYS = 365

# 80% empirical prediction interval: 10th and 90th percentile of the
# signed backtest error (actual / predicted - 1), per horizon.
INTERVAL_QUANTILES = (0.10, 0.90)

MLFLOW_EXPERIMENT = "demand_forecast_multi_horizon"
# R15 production model (issue #229), served by forecast-service (Ajith, A2).
REGISTERED_MODEL_NAME = "demand_forecast"
REGISTRY_DIR = PROJECT_ROOT / "models" / "registry"
SHARE_WINDOW_DAYS = 90
HOLDOUT_DAYS = 90
HORIZON_BUCKETS = ((1, 1), (2, 7), (8, 30), (31, 90))

# Pair-days with a smaller prediction are left out of interval calibration,
# since actual/predicted is unstable near zero.
MIN_CALIBRATION_PREDICTION = 0.5