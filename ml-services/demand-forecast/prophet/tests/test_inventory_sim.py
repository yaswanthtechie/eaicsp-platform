"""Tests for the business-value simulation: correctness and NO FUTURE DATA."""

import numpy as np
import pandas as pd
import pytest

from src.inventory_sim import Costs, Policy, first_decision_day, simulate, summarise
from src.walk_forward_forecasts import (
    build_walk_forward_forecasts,
    naive_ma_forecasts,
    walk_forward_prophet_weights,
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

@pytest.mark.parametrize(
    "make_forecast",
    [naive_weekly_forecasts, naive_ma_forecasts],
)
@pytest.mark.parametrize("make_forecast", [naive_weekly_forecasts, naive_ma_forecasts])
def test_simulation_never_reads_future_demand(make_forecast):
    """Perturb demand from day T on: every decision made on days <= T is unchanged."""
    y = _series()
    origins = np.arange(FIRST_ORIGIN, len(y) - 1)
    t0 = first_decision_day(FIRST_ORIGIN, POLICY)
    T = t0 + 80

    y2 = y.copy()
    y2[T:] = y2[T:] * 3 + 500  # the future changes completely

    a = simulate(y, make_forecast(y, origins, H), FIRST_ORIGIN, POLICY)
    b = simulate(y2, make_forecast(y2, origins, H), FIRST_ORIGIN, POLICY)
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



@pytest.mark.parametrize("cut", [365, 380, 395])  # refit day, mid-block, next refit day
def test_model_forecasts_only_use_past_data(cut):
    """The forecast made at origin `cut` must not change when ANY later day changes."""
    n = 420
    y = _series(n=n, seed=7)
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    kwargs = dict(horizon=H, refit_every=30)

    a = build_walk_forward_forecasts(dates, y, 365, **kwargs)

    y2 = y.copy()
    y2[cut + 1:] = y2[cut + 1:] * 5 + 1000  # everything after the origin changes

    b = build_walk_forward_forecasts(dates, y2, 365, **kwargs)

    for name in (
        "prophet",
        "xgboost",
        "ensemble",
        "ensemble_50_50",
        "naive_weekly",
        "naive_ma28",
    ):
        np.testing.assert_allclose(
            a[name][:cut + 1],
            b[name][:cut + 1],
            rtol=1e-9,
            err_msg=name,
        )
def test_walk_forward_weights_use_only_realised_errors():
    n, first, refit = 500, 120, 7
    y = _series(n=n, seed=11)

    good = np.full((n, H), np.nan)
    for o in range(first, n - 1):
        w = y[o + 1:o + 1 + H]
        good[o] = np.pad(w, (0, H - len(w)), constant_values=w[-1])

    bad = good * 1.5
    w1 = walk_forward_prophet_weights(
        y, good, bad, first, refit, lookback=60
    )

    assert w1[first] == 0.5  # no realised errors yet: default weight
    assert w1[-2] == 1.0  # the accurate forecast wins once errors are known

    # On each refit date make every later day unknown (NaN):
    # any peek poisons the weight.
    for start in range(first, n - 1, refit):
        y_unknown = y.copy()
        y_unknown[start + 1:] = np.nan
        w2 = walk_forward_prophet_weights(
            y_unknown, good, bad, first, refit, lookback=60
        )
        assert w2[start] == w1[start], (
            f"weight chosen on day {start} used data after day {start}"
        )


def test_missing_forecast_raises_instead_of_ordering_nothing():
    y = _series()
    f = _naive(y)
    f[first_decision_day(FIRST_ORIGIN, POLICY) + 10] = np.nan

    with pytest.raises(ValueError, match="no forecast"):
        simulate(y, f, FIRST_ORIGIN, POLICY)


def _write_group_csv(path, dates, qty):
    pd.DataFrame({
        "group": "g1",
        "date": dates,
        "quantity_sold": qty,
    }).to_csv(path, index=False)


def test_tiers_from_csv_rejects_duplicate_date_hiding_a_gap(tmp_path):
    from src.business_value_simulation import tiers_from_csv

    dates = list(pd.date_range("2015-01-01", periods=1200, freq="D"))
    dates[500] = dates[499]  # one day twice, one day missing; row count still matches

    _write_group_csv(tmp_path / "g.csv", dates, 5)

    with pytest.raises(ValueError, match="duplicate"):
        tiers_from_csv(tmp_path / "g.csv")


def test_tiers_from_csv_rejects_series_too_short_to_replay(tmp_path):
    from src.business_value_simulation import tiers_from_csv

    _write_group_csv(
        tmp_path / "g.csv",
        pd.date_range("2015-01-01", periods=800, freq="D"),
        5,
    )

    with pytest.raises(ValueError, match="need at least"):
        tiers_from_csv(tmp_path / "g.csv")


def test_forecast_cache_name_changes_with_data_and_config(monkeypatch):
    import src.business_value_simulation as bv

    y = _series()
    base = bv.forecast_cache_path("slow movers (~5/day)", y)

    assert bv.forecast_cache_path("slow movers (~5/day)", y) == base  # stable
    assert bv.forecast_cache_path("slow movers (~5/day)", y + 1) != base  # data changed

    monkeypatch.setattr(bv, "REFIT_EVERY_DAYS", 14)
    assert bv.forecast_cache_path("slow movers (~5/day)", y) != base  # config changed


def test_simulation_results_are_logged_to_mlflow(tmp_path):
    import mlflow
    import src.business_value_simulation as bv

    mlflow.set_tracking_uri(
        f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}"
    )
    mlflow.create_experiment(
        bv.MLFLOW_EXPERIMENT,
        artifact_location=(tmp_path / "artifacts").as_uri(),
    )

    tier, approach = "slow movers (~5/day)", "ensemble"

    headline = pd.DataFrame([{
        "tier": tier,
        "approach": approach,
        "stockout_days": 3,
        "lost_units": 9.0,
        "avg_inventory": 14.5,
        "holding_cost": 88.4,
    }])

    equal = pd.DataFrame([{
        "tier": tier,
        "approach": approach,
        "lead_time": 7,
        "avg_inventory_needed": 13.4,
    }])

    report = tmp_path / "metrics_headline.csv"
    headline.to_csv(report, index=False)

    bv.log_to_mlflow(
        {"unit_value": 10.0, "policy": {"lead_time": 7}},
        headline,
        equal,
        [report],
    )

    run = mlflow.search_runs(
        experiment_names=[bv.MLFLOW_EXPERIMENT]
    ).iloc[0]

    assert run["params.unit_value"] == "10.0"
    assert run["metrics.slow_movers_5_day.ensemble.lost_units"] == 9.0
    assert run["metrics.slow_movers_5_day.ensemble.stock_needed_at_target_fill"] == 13.4

    assert "metrics_headline.csv" in {
        a.path for a in mlflow.artifacts.list_artifacts(run_id=run["run_id"])
    }


def test_summary_names_the_tiers_where_the_forecast_does_not_help():
    from src.business_value_summary import build_summary, tier_verdicts

    rows = []
    for tier, stock in {
        "fast": {
            "ensemble": 80,
            "prophet": 90,
            "xgboost": 95,
            "naive_weekly": 180,
            "naive_ma28": 110,
        },
        "medium": {
            "ensemble": 24,
            "prophet": 24,
            "xgboost": 28,
            "naive_weekly": 49,
            "naive_ma28": 28,
        },
        "slow": {
            "ensemble": 14.5,
            "prophet": 14.6,
            "xgboost": 15.3,
            "naive_weekly": 23,
            "naive_ma28": 15.5,
        },
    }.items():
        for approach, s in stock.items():
            # A 3-day lead-time row first: summary must only read the 7-day rows.
            rows.append({
                "tier": tier,
                "approach": approach,
                "lead_time": 3,
                "avg_inventory_needed": s / 2,
                "holding_cost_over_window": s * 3,
                "window_days": 1116,
            })
            rows.append({
                "tier": tier,
                "approach": approach,
                "lead_time": 7,
                "avg_inventory_needed": s,
                "holding_cost_over_window": s * 6,
                "window_days": 1108,
            })

    equal = pd.DataFrame(rows)
    v = tier_verdicts(equal).set_index("tier")["verdict"]

    assert v["fast"] == "the ensemble pays off"
    assert v["medium"].startswith(
        "forecasting helps, but the ensemble adds nothing"
    )
    assert v["slow"].startswith("little or no gain")

    text = build_summary(
        equal,
        {"unit_value": 10.0, "annual_holding_rate": 0.2},
    )
    assert "slow: little or no gain" in text and "1108 days" in text        