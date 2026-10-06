"""Configuration for daily multi-horizon forecasting. No magic numbers elsewhere."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_PATH = PROJECT_ROOT / "data" / "m5_daily_sales.csv"
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

# Rolling-origin backtest:
# refit at each cutoff, forecast 90 days, score each horizon.
BACKTEST_CUTOFFS = 24
BACKTEST_STEP_DAYS = 30
CALIBRATION_CUTOFFS = 16
MIN_TRAINING_DAYS = 730

# 80% empirical prediction interval: 10th and 90th percentile of the
# signed backtest error (actual / predicted - 1), per horizon.
INTERVAL_QUANTILES = (0.10, 0.90)

MLFLOW_EXPERIMENT = "demand_forecast_multi_horizon"