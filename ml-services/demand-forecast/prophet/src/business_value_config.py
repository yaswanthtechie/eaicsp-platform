"""Configuration for the business-value (inventory) simulation."""

from src.multi_horizon_config import PROJECT_ROOT

REPORT_DIR = PROJECT_ROOT / "reports" / "business_value"

# --- Business assumptions (STATED, not measured: the data has no prices) ---
UNIT_VALUE = 10.0            # currency per unit
ANNUAL_HOLDING_RATE = 0.20   # 20% of item value per year
UNIT_MARGIN = 3.0            # profit lost per unit of lost sale
DAYS_PER_YEAR = 365

# --- Replenishment policy ---
LEAD_TIME_DAYS = 7           # order placed on day t arrives at start of t+7
LEAD_TIME_SENSITIVITY = (3, 7, 14)
SERVICE_QUANTILE = 0.95
SERVICE_QUANTILE_GRID = (
    0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.95,
    0.97, 0.98, 0.99, 0.995, 0.999,
)
ERROR_WINDOW_ORIGINS = 365   # how many past forecast errors size the safety stock
MIN_ERROR_SAMPLES = 60
TARGET_FILL_RATE = 0.98      # equal-service comparison point

# --- Walk-forward forecasting ---
FIRST_ORIGIN = 729           # day index of the first fit (730 days of history)
MAX_HORIZON = 15             # must be >= largest lead time + 1
REFIT_EVERY_DAYS = 7
XGB_HISTORY_DAYS = 30        # longest lag/rolling window in the feature set

# --- SKU-volume tiers (binomial thinning of the real daily series) ---
VOLUME_TIERS = {
    "aggregate (~34,000/day)": None,   # None = real series as-is
    "fast movers (~200/day)": 200.0,
    "medium movers (~30/day)": 30.0,
    "slow movers (~5/day)": 5.0,
}
THINNING_SEED = 20260

APPROACHES = ("ensemble", "prophet", "xgboost", "naive_weekly", "naive_ma28")
FALLBACK_ENSEMBLE_WEIGHTS = {"prophet": 0.5, "xgb": 0.5}