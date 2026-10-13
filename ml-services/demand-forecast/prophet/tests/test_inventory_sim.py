"""Tests for the business-value simulation: correctness and NO FUTURE DATA."""

import numpy as np
import pandas as pd
import pytest

from src.inventory_sim import Costs, Policy, first_decision_day, simulate, summarise
from src.walk_forward_forecasts import (
    build_walk_forward_forecasts,
    naive_ma_forecasts,
    naive_weekly_forecasts,
)

H = 10
FIRST_ORIGIN = 120
POLICY = Policy(lead_time=3, service_quantile=0.9, error_window=60, min_error_samples=20)


def _series(n=420, seed=0):
    rng = np.random.default_rng(seed)
    base = 100 + 20 * np.sin(2 * np.pi * np.arange(n) / 7)
    return rng.poisson(base).astype(float)


def _naive(y):
    origins = np.arange(FIRST_ORIGIN, len(y) - 1)
    return naive_weekly_forecasts(y, origins, H)


def test_naive_forecasts_only_use_past():
    y = _series()
    cut = 250
    y2 = y.copy()
    y2[cut + 1 :] = 1e9                      # corrupt everything after origin `cut`
    for fn in (naive_weekly_forecasts, naive_ma_forecasts):
        a = fn(y, np.arange(FIRST_ORIGIN, len(y) - 1), H)
        b = fn(y2, np.arange(FIRST_ORIGIN, len(y) - 1), H)
        np.testing.assert_array_equal(a[: cut + 1], b[: cut + 1])


def test_naive_weekly_is_same_weekday_last_week():
    y = np.arange(100, dtype=float)
    f = naive_weekly_forecasts(y, np.array([50]), 9)
    assert f[50, 0] == y[44]                 # day 51 -> day 44
    assert f[50, 6] == y[50]                 # day 57 -> day 50
    assert f[50, 7] == y[44]                 # day 58 -> day 44 (not 51)
    for k in range(1, 10):
        assert (50 + k - 7 * np.ceil(k / 7)) <= 50   # never a future day


def test_simulation_never_reads_future_demand():
    """Perturb demand from day T on: every decision made on days <= T is unchanged."""
    y = _series()
    t0 = first_decision_day(FIRST_ORIGIN, POLICY)
    T = t0 + 80
    y2 = y.copy()
    y2[T:] = y2[T:] * 3 + 500                # the future changes completely
    a = simulate(y, _naive(y), FIRST_ORIGIN, POLICY)
    b = simulate(y2, _naive(y2), FIRST_ORIGIN, POLICY)
    cols = ["order_qty", "order_up_to", "lead_time_forecast", "safety_ratio"]
    pd.testing.assert_frame_equal(a[a.day <= T][cols], b[b.day <= T][cols])
    assert (a[a.day < T].on_hand_end.values == b[b.day < T].on_hand_end.values).all()


def test_conservation_and_no_negative_stock():
    y = _series()
    log = simulate(y, _naive(y), FIRST_ORIGIN, POLICY)
    assert (log.on_hand_end >= 0).all()
    assert np.allclose(log.sold + log.lost, log.demand)
    start = log.on_hand_end.shift(1)
    arrivals = log.order_qty.shift(POLICY.lead_time).fillna(0)
    ok = log.index > POLICY.lead_time + 1
    assert np.allclose((log.on_hand_end - start - arrivals + log.sold)[ok], 0, atol=1e-9)


def test_perfect_forecast_beats_naive_on_cost():
    y = _series(seed=3)
    n = len(y)
    perfect = np.full((n, H), np.nan)
    for o in range(FIRST_ORIGIN, n - 1):
        w = y[o + 1 : o + 1 + H]
        perfect[o] = np.pad(w, (0, H - len(w)), constant_values=w[-1])
    p = summarise(simulate(y, perfect, FIRST_ORIGIN, POLICY))
    q = summarise(simulate(y, _naive(y), FIRST_ORIGIN, POLICY))
    assert p["total_cost"] <= q["total_cost"]
    assert p["lost_units"] == 0              # perfect foresight never stocks out


def test_higher_service_quantile_means_more_stock_fewer_lost_sales():
    y = _series(seed=5)
    f = _naive(y)
    lo = summarise(simulate(y, f, FIRST_ORIGIN, Policy(3, 0.6, 60, 20)))
    hi = summarise(simulate(y, f, FIRST_ORIGIN, Policy(3, 0.99, 60, 20)))
    assert hi["avg_inventory"] > lo["avg_inventory"]
    assert hi["lost_units"] <= lo["lost_units"]


def test_holding_cost_assumption():
    c = Costs(unit_value=10.0, annual_holding_rate=0.20)
    assert c.holding_per_unit_day == pytest.approx(10 * 0.2 / 365)
    log = pd.DataFrame(
        {"demand": [10.0, 10.0], "sold": [10.0, 10.0], "lost": [0.0, 0.0],
         "on_hand_end": [100.0, 200.0], "stockout": [False, False]}
    )
    m = summarise(log, c)
    assert m["holding_cost"] == pytest.approx(300 * 10 * 0.2 / 365)
    assert m["avg_inventory"] == 150 and m["stockout_days"] == 0


def test_model_forecasts_only_use_past_data():
    """Prophet+XGBoost walk-forward forecasts for early origins ignore later data."""
    n = 420
    y = _series(n=n, seed=7)
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    kwargs = dict(horizon=H, refit_every=30, weights={"prophet": 0.5, "xgb": 0.5})
    a = build_walk_forward_forecasts(dates, y, 365, **kwargs)
    y2 = y.copy()
    y2[380:] = y2[380:] * 5 + 1000           # corrupt data after day 380
    b = build_walk_forward_forecasts(dates, y2, 365, **kwargs)
    for name in ("prophet", "xgboost", "ensemble", "naive_weekly", "naive_ma28"):
        np.testing.assert_allclose(a[name][365:380], b[name][365:380], rtol=1e-9, err_msg=name)