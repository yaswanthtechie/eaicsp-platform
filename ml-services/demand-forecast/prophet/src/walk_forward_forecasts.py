"""Leak-free walk-forward forecasts for the inventory simulation.

Convention:
    F[o, k-1] = forecast for day (o + k), made at the END of day o,
                using only demand observed on days 0..o.
"""

from __future__ import annotations

import logging
from typing import Iterable

import holidays
import numpy as np
import pandas as pd
from prophet import Prophet
from xgboost import XGBRegressor

from src.business_value_config import (
    APPROACHES,
    FALLBACK_ENSEMBLE_WEIGHTS,
    MAX_HORIZON,
    REFIT_EVERY_DAYS,
    XGB_HISTORY_DAYS,
)
from src.ensemble import weighted_ensemble
from src.multi_horizon_config import PROPHET_PARAMS, XGB_PARAMS
from src.multi_horizon_inference import FEATURES, create_daily_features

logging.getLogger("cmdstanpy").setLevel(logging.ERROR)
logging.getLogger("prophet").setLevel(logging.ERROR)

_US_HOLIDAYS = holidays.US()


def load_ensemble_weights(path=None) -> dict[str, float]:
    """Promoted ensemble weights if the file exists, else 50/50."""
    from src.multi_horizon import load_ensemble_weights as _load
    from src.multi_horizon_config import WEIGHTS_PATH

    try:
        if (path or WEIGHTS_PATH).exists():
            return _load()
    except Exception:
        pass
    return dict(FALLBACK_ENSEMBLE_WEIGHTS)


# ---------------------------------------------------------------------------
# Naive baselines (use only y[0..o])
# ---------------------------------------------------------------------------

def naive_weekly_forecasts(y: np.ndarray, origins: np.ndarray, horizon: int) -> np.ndarray:
    """Same weekday, most recent observed week (seasonal naive, season = 7)."""
    out = np.full((len(y), horizon), np.nan)
    for k in range(1, horizon + 1):
        back = 7 * int(np.ceil(k / 7))   # latest same-weekday day that is <= o
        src = origins + k - back
        out[origins, k - 1] = y[src]
    return out


def naive_ma_forecasts(y: np.ndarray, origins: np.ndarray, horizon: int, window: int = 28) -> np.ndarray:
    """Flat forecast: mean of the last `window` observed days."""
    csum = np.concatenate([[0.0], np.cumsum(y, dtype=float)])
    means = (csum[origins + 1] - csum[origins + 1 - window]) / window
    out = np.full((len(y), horizon), np.nan)
    out[origins, :] = means[:, None]
    return out


# ---------------------------------------------------------------------------
# Prophet
# ---------------------------------------------------------------------------

def _holiday_flags(dates: pd.DatetimeIndex) -> np.ndarray:
    return np.array([int(d.date() in _US_HOLIDAYS) for d in dates], dtype=int)


def _fit_prophet(dates: pd.DatetimeIndex, y: np.ndarray) -> Prophet:
    model = Prophet(**PROPHET_PARAMS)
    model.add_regressor("is_holiday")
    frame = pd.DataFrame({"ds": dates, "y": y.astype(float), "is_holiday": _holiday_flags(dates)})
    model.fit(frame)
    return model


def _prophet_predict(model: Prophet, future_dates: pd.DatetimeIndex) -> np.ndarray:
    future = pd.DataFrame({"ds": future_dates, "is_holiday": _holiday_flags(future_dates)})
    return np.maximum(0.0, model.predict(future)["yhat"].to_numpy(dtype=float))


# ---------------------------------------------------------------------------
# XGBoost (fast vectorised version of the repo's recursive forecast)
# ---------------------------------------------------------------------------

def _fit_xgb(dates: pd.DatetimeIndex, y: np.ndarray) -> XGBRegressor:
    frame = create_daily_features(
        pd.DataFrame({"date": dates, "quantity_sold": y.astype(float)}),
        drop_missing=True,
    )
    model = XGBRegressor(**XGB_PARAMS)
    model.fit(frame[FEATURES], frame["quantity_sold"])
    return model


def _xgb_recursive(model, y, origins, calendar, horizon) -> np.ndarray:
    """Recursive H-step forecasts for many origins at once.

    Predictions are clipped at 0 and rounded to 2 dp, then fed back as lags,
    exactly like src.multi_horizon_inference.predict_future_xgboost.
    """
    w = XGB_HISTORY_DAYS
    n = len(origins)
    buf = np.empty((n, w + horizon))
    for i, o in enumerate(origins):
        buf[i, :w] = y[o - w + 1 : o + 1]      # last 30 ACTUAL days up to the origin
    out = np.empty((n, horizon))
    for j in range(horizon):
        day = origins + 1 + j
        last7 = buf[:, w + j - 7 : w + j]
        feats = pd.DataFrame(
            {
                "lag_1": buf[:, w + j - 1],
                "lag_7": buf[:, w + j - 7],
                "lag_30": buf[:, w + j - 30],
                "rolling_mean_7": last7.mean(axis=1),
                "rolling_mean_30": buf[:, j : w + j].mean(axis=1),
                "rolling_std_7": last7.std(axis=1, ddof=1),
                "is_holiday": calendar["is_holiday"].to_numpy()[day],
                "day_of_week": calendar["day_of_week"].to_numpy()[day],
                "month": calendar["month"].to_numpy()[day],
                "quarter": calendar["quarter"].to_numpy()[day],
                "year": calendar["year"].to_numpy()[day],
            }
        )[FEATURES]
        pred = np.round(np.maximum(0.0, model.predict(feats)), 2)
        out[:, j] = pred
        buf[:, w + j] = pred                   # feed prediction back in
    return out


def _calendar(dates: pd.DatetimeIndex, horizon: int) -> pd.DataFrame:
    full = pd.date_range(dates[0], periods=len(dates) + horizon + 1, freq="D")
    return pd.DataFrame(
        {
            "is_holiday": _holiday_flags(full),
            "day_of_week": full.dayofweek,
            "month": full.month,
            "quarter": full.quarter,
            "year": full.year,
        }
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_walk_forward_forecasts(
    dates: pd.DatetimeIndex,
    y: np.ndarray,
    first_origin: int,
    *,
    horizon: int = MAX_HORIZON,
    refit_every: int = REFIT_EVERY_DAYS,
    weights: dict[str, float] | None = None,
    approaches: Iterable[str] = APPROACHES,
) -> dict[str, np.ndarray]:
    """Return {approach: F}, F shape (len(y), horizon); NaN before first_origin."""
    approaches = tuple(approaches)
    y = np.asarray(y, dtype=float)
    n = len(y)
    weights = weights or load_ensemble_weights()
    origins_all = np.arange(first_origin, n - 1)
    result: dict[str, np.ndarray] = {}

    if "naive_weekly" in approaches:
        result["naive_weekly"] = naive_weekly_forecasts(y, origins_all, horizon)
    if "naive_ma28" in approaches:
        result["naive_ma28"] = naive_ma_forecasts(y, origins_all, horizon)

    need_prophet = any(a in approaches for a in ("prophet", "ensemble"))
    need_xgb = any(a in approaches for a in ("xgboost", "ensemble"))
    prophet_f = np.full((n, horizon), np.nan)
    xgb_f = np.full((n, horizon), np.nan)
    calendar = _calendar(dates, horizon) if need_xgb else None

    for start in range(first_origin, n - 1, refit_every):
        block = np.arange(start, min(start + refit_every, n - 1))
        train_dates, train_y = dates[: start + 1], y[: start + 1]   # data through day `start` ONLY
        if need_prophet:
            model = _fit_prophet(train_dates, train_y)
            span = pd.date_range(
                dates[start] + pd.Timedelta(days=1),
                periods=len(block) - 1 + horizon,
                freq="D",
            )
            pred = _prophet_predict(model, span)
            for i, o in enumerate(block):
                prophet_f[o] = pred[i : i + horizon]
        if need_xgb:
            model = _fit_xgb(train_dates, train_y)
            xgb_f[block] = _xgb_recursive(model, y, block, calendar, horizon)

    if "prophet" in approaches:
        result["prophet"] = prophet_f
    if "xgboost" in approaches:
        result["xgboost"] = xgb_f
    if "ensemble" in approaches:
        result["ensemble"] = np.maximum(
            0.0,
            weighted_ensemble(prophet_f, xgb_f, weights["prophet"], weights["xgb"]),
        )
    return result