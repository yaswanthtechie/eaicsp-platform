"""What is a better forecast worth?  Inventory replay for every approach.

Run from the prophet/ folder:   python -m src.business_value_simulation
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict
from datetime import timedelta
from importlib import metadata

import holidays
import mlflow
import numpy as np
import pandas as pd

from src.business_value_config import (
    ANNUAL_HOLDING_RATE, APPROACHES, FIRST_ORIGIN, LEAD_TIME_DAYS,
    LEAD_TIME_SENSITIVITY, MAX_HORIZON, MIN_REPLAY_DAYS, MIN_WEIGHT_ORIGINS,
    MLFLOW_EXPERIMENT, REFIT_EVERY_DAYS, REPORT_DIR, SERVICE_QUANTILE,
    SERVICE_QUANTILE_GRID, TARGET_FILL_RATE, THINNING_SEED, UNIT_MARGIN,
    UNIT_VALUE, VOLUME_TIERS, WEIGHT_GRID, WEIGHT_LOOKBACK_ORIGINS,
)
from src.inventory_sim import (
    Costs, Policy, lead_time_forecast_and_actual, simulate, summarise,
)
from src.multi_horizon_config import PROPHET_PARAMS, XGB_PARAMS
from src.multi_horizon_data import load_daily_data
from src.walk_forward_forecasts import build_walk_forward_forecasts

ORACLE = "perfect_foresight (ceiling, not a real forecast)"
COSTS = Costs()
_US_HOLIDAYS = holidays.US()


def make_tiers(daily):
    """Full series plus binomially-thinned (lower-volume) versions of it."""
    dates = pd.DatetimeIndex(daily["date"])
    y = daily["quantity_sold"].to_numpy(dtype=float)
    tiers = {}
    for i, (name, mean_units) in enumerate(VOLUME_TIERS.items()):
        if mean_units is None:
            tiers[name] = (dates, y)
        else:
            rng = np.random.default_rng(THINNING_SEED + i)
            p = mean_units / y.mean()
            tiers[name] = (dates, rng.binomial(y.astype(np.int64), p).astype(float))
    return tiers


def tiers_from_csv(path):
    """Real SKU groups: CSV with columns group,date,quantity_sold (one row per day, no gaps)."""
    df = pd.read_csv(path, parse_dates=["date"])
    min_days = FIRST_ORIGIN + MIN_REPLAY_DAYS
    out = {}

    for group, g in df.groupby("group"):
        g = g.sort_values("date")

        if g["date"].duplicated().any():
            raise ValueError(f"group {group!r} has duplicate dates")

        idx = pd.date_range(g["date"].min(), g["date"].max(), freq="D")
        if len(idx) != len(g):
            raise ValueError(f"group {group!r} has date gaps")

        if len(g) < min_days:
            raise ValueError(
                f"group {group!r} has {len(g)} days; need at least {min_days}"
            )

        if g["quantity_sold"].isna().any() or (g["quantity_sold"] < 0).any():
            raise ValueError(
                f"group {group!r} has missing or negative quantities"
            )

        out[str(group)] = (
            pd.DatetimeIndex(g["date"]),
            g["quantity_sold"].to_numpy(dtype=float),
        )

    return out

def oracle_forecasts(y, first_origin, horizon):
    """Upper bound only: reads the future ON PURPOSE. Never a candidate approach."""
    n = len(y)
    f = np.full((n, horizon), np.nan)
    for o in range(first_origin, n - 1):
        w = y[o + 1 : o + 1 + horizon]
        f[o] = np.pad(w, (0, horizon - len(w)), constant_values=w[-1])
    return f


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def forecast_cache_path(name, y):
    """Cache key includes forecast settings, library versions and input data."""
    key = {
        "first_origin": FIRST_ORIGIN,
        "horizon": MAX_HORIZON,
        "refit_every": REFIT_EVERY_DAYS,
        "approaches": list(APPROACHES),
        "weight_grid": list(WEIGHT_GRID),
        "weight_lookback": WEIGHT_LOOKBACK_ORIGINS,
        "min_weight_origins": MIN_WEIGHT_ORIGINS,
        "prophet_params": PROPHET_PARAMS,
        "xgb_params": XGB_PARAMS,
        "versions": library_versions(),
    }

    digest = hashlib.sha256(
        json.dumps(key, sort_keys=True, default=str).encode()
    )
    digest.update(np.ascontiguousarray(y, dtype=float).tobytes())

    return (
        REPORT_DIR
        / "cache"
        / f"{_slug(name)}_{digest.hexdigest()[:12]}.npz"
    )


def library_versions():
    return {
        pkg: metadata.version(pkg)
        for pkg in ("prophet", "xgboost", "numpy", "pandas")
    }


def get_forecasts(name, dates, y, refresh):
    """Fit walk-forward models and cache forecasts using a reproducible key."""
    cache = forecast_cache_path(name, y)

    if cache.exists() and not refresh:
        print(f"  cache hit: {name}", flush=True)
        with np.load(cache) as z:
            return {k: z[k] for k in z.files}

    print(f"  fitting walk-forward models for {name} ...", flush=True)

    forecasts = build_walk_forward_forecasts(
        dates,
        y,
        FIRST_ORIGIN,
        horizon=MAX_HORIZON,
        refit_every=REFIT_EVERY_DAYS,
        approaches=APPROACHES,
    )

    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, **forecasts)

    return forecasts

def measurement_mask(log, policy):
    """Skip the first lead-time of days: the opening stock is a free assumption."""
    return (log["day"] >= log["day"].iloc[0] + policy.lead_time + 1).to_numpy()


def forecast_accuracy(y, f, policy, first_day):
    """WAPE of the 1-day and lead-time-total forecasts over the measured window."""
    fcum, _ = lead_time_forecast_and_actual(y, f, policy.lead_time)
    days = np.arange(first_day + policy.lead_time + 1, len(y) - policy.lead_time - 1)
    one_day = np.abs(f[days - 1, 0] - y[days]).sum() / y[days].sum()
    csum = np.concatenate([[0.0], np.cumsum(y)])
    actual_lt = csum[days + policy.lead_time + 1] - csum[days]
    lt = np.abs(fcum[days - 1] - actual_lt).sum() / actual_lt.sum()
    return {"wape_1day": float(one_day), "wape_lead_time_total": float(lt)}


def segment_rows(tier, approach, log, mask, dates, base):
    """Same metrics split by calendar segment: where does the forecast not help?"""
    d = dates[log["day"].to_numpy()]
    near_holiday = np.array(
        [
            any((x.date() + timedelta(days=k)) in _US_HOLIDAYS for k in range(-3, 4))
            for x in d
        ]
    )
    segments = {
        "weekday (Mon-Fri)": d.dayofweek < 5,
        "weekend (Sat-Sun)": d.dayofweek >= 5,
        "within 3 days of a US holiday": near_holiday,
        "not near a holiday": ~near_holiday,
        "Nov-Dec peak season": d.month.isin([11, 12]),
        "Jan-Oct": ~d.month.isin([11, 12]),
    }
    for yr in sorted(set(d.year)):
        segments[f"year {yr}"] = d.year == yr
    out = []
    for seg, sel in segments.items():
        sel = np.asarray(sel) & mask
        if sel.sum() < 10:
            continue
        out.append({"tier": tier, "approach": approach, "segment": seg, **summarise(log, COSTS, sel)})
    return out


def run_tier(name, dates, y, forecasts, lead_times):
    rows, frontier, segs, acc = [], [], [], []
    all_f = {
    k: v
    for k, v in forecasts.items()
    if not k.startswith("_")
}  # "_..." keys are metadata, not forecasts
    all_f[ORACLE] = oracle_forecasts(y, FIRST_ORIGIN, MAX_HORIZON)
    for lt in lead_times:
        for approach, f in all_f.items():
            for q in SERVICE_QUANTILE_GRID:
                pol = Policy(lead_time=lt, service_quantile=q)
                log = simulate(y, f, FIRST_ORIGIN, pol, COSTS)
                mask = measurement_mask(log, pol)
                m = summarise(log, COSTS, mask)
                base = {"tier": name, "approach": approach, "lead_time": lt, "service_quantile": q}
                frontier.append({**base, **m})
                if lt == LEAD_TIME_DAYS and np.isclose(q, SERVICE_QUANTILE):
                    rows.append({**base, **m})
                    acc.append({**base, **forecast_accuracy(y, f, pol, log["day"].iloc[0])})
                    segs.extend(segment_rows(name, approach, log, mask, dates, base))
    return rows, frontier, segs, acc


def equal_fill_rate_table(frontier, target=TARGET_FILL_RATE):
    """Average inventory each approach needs to reach `target` fill rate (interpolated)."""
    rows = []
    for (tier, approach, lt), g in frontier.groupby(["tier", "approach", "lead_time"]):
        g = g.sort_values("service_quantile")
        fr = np.maximum.accumulate(g["fill_rate"].to_numpy())
        inv = g["avg_inventory"].to_numpy()
        days = g["days"].iloc[0]
        need = np.nan if (fr.max() < target or fr.min() > target) else float(np.interp(target, fr, inv))
        rows.append({
            "tier": tier, "approach": approach, "lead_time": lt,
            "target_fill_rate": target, "avg_inventory_needed": need,
            "holding_cost_over_window": need * days * COSTS.holding_per_unit_day,
            "window_days": int(days),
        })
    return pd.DataFrame(rows)


def log_to_mlflow(assumptions, headline, equal, report_files):
    """One MLflow run per simulation: assumptions as params, business metrics as metrics, CSVs as artifacts."""
    mlflow.set_experiment(MLFLOW_EXPERIMENT)
    with mlflow.start_run(run_name="business_value_simulation"):
        mlflow.log_params(
            {k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in assumptions.items()}
        )
        for row in headline.itertuples(index=False):
            prefix = f"{_slug(row.tier)}.{_slug(row.approach)}"
            mlflow.log_metrics({
                f"{prefix}.stockout_days": float(row.stockout_days),
                f"{prefix}.lost_units": float(row.lost_units),
                f"{prefix}.avg_inventory": float(row.avg_inventory),
                f"{prefix}.holding_cost": float(row.holding_cost),
            })
        at_target = equal[(equal.lead_time == LEAD_TIME_DAYS) & equal.avg_inventory_needed.notna()]
        for row in at_target.itertuples(index=False):
            mlflow.log_metric(
                f"{_slug(row.tier)}.{_slug(row.approach)}.stock_needed_at_target_fill",
                float(row.avg_inventory_needed),
            )
        for path in report_files:
            mlflow.log_artifact(str(path))

def library_versions():
    packages = (
        "mlflow",
        "numpy",
        "pandas",
        "holidays",
        "prophet",
        "xgboost",
    )
    versions = {}

    for package in packages:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = "not-installed"

    return versions
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-csv", help="daily series per SKU group: group,date,quantity_sold")
    ap.add_argument("--refresh", action="store_true", help="refit models, ignore cache")
    args = ap.parse_args()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    tiers = tiers_from_csv(args.input_csv) if args.input_csv else make_tiers(load_daily_data())

    headline, frontier, segs, acc, chosen_weights = [], [], [], [], {}
    for name, (dates, y) in tiers.items():
        print(f"tier: {name}  (mean {y.mean():.1f}/day, {len(y)} days)", flush=True)
        f = get_forecasts(name, dates, y, args.refresh)
        if "_prophet_weight" in f:
            chosen_weights[name] = round(float(np.nanmean(f["_prophet_weight"])), 3)
        r, fr, s, a = run_tier(name, dates, y, f, LEAD_TIME_SENSITIVITY)
        headline += r; frontier += fr; segs += s; acc += a

    frontier = pd.DataFrame(frontier)
    headline = pd.DataFrame(headline)
    headline = headline[headline.lead_time == LEAD_TIME_DAYS]
    equal = equal_fill_rate_table(frontier)

    outputs = {
        "metrics_headline.csv": headline,
        "frontier_all_service_levels.csv": frontier,
        "segments.csv": pd.DataFrame(segs),
        "forecast_accuracy.csv": pd.DataFrame(acc),
        "equal_fill_rate.csv": equal,
    }
    for file_name, table in outputs.items():
        table.to_csv(REPORT_DIR / file_name, index=False)

    assumptions = {
        "unit_value": UNIT_VALUE, "annual_holding_rate": ANNUAL_HOLDING_RATE,
        "unit_margin_lost_per_unit": UNIT_MARGIN, "lead_time_days": LEAD_TIME_DAYS,
        "headline_service_quantile": SERVICE_QUANTILE,
        "ensemble_weighting": (
            "walk-forward: Prophet weight re-chosen at every refit from realised "
            f"errors only, grid {WEIGHT_GRID[0]}-{WEIGHT_GRID[-1]}, lookback "
            f"{WEIGHT_LOOKBACK_ORIGINS} origins; ensemble_50_50 = fixed 0.5/0.5"
        ),
        "ensemble_mean_prophet_weight": chosen_weights,
        "refit_every_days": REFIT_EVERY_DAYS, "first_origin_day_index": FIRST_ORIGIN,
        "target_fill_rate": TARGET_FILL_RATE, "policy": asdict(Policy()),
        "volume_tiers": "binomial thinning of ONE aggregate series (not real SKUs)"
        if not args.input_csv else f"real groups from {args.input_csv}",
        "library_versions": library_versions(),
    }
    (REPORT_DIR / "assumptions.json").write_text(json.dumps(assumptions, indent=2))

    log_to_mlflow(assumptions, headline, equal,
                  [REPORT_DIR / n for n in (*outputs, "assumptions.json")])
    print("wrote", REPORT_DIR)
if __name__ == "__main__":
    main()