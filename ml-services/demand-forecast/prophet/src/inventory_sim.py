"""Day-by-day inventory replay driven by a forecast matrix.

Timing of day t (all decisions use information from days <= t-1 only):

    1. Orders due today arrive (start of day).
    2. Policy:
         lead-time forecast = sum(F[t-1, 0..L])          (days t..t+L)
         ratio quantile     = q-quantile of past (actual_cum / forecast_cum),
                              using only windows fully realised by day t-1
         order-up-to S      = lead-time forecast * ratio quantile
         if inventory position < S: order the shortfall (integer units),
         arriving at the start of day t+L.
    3. Day t demand is served from on-hand stock; the rest is a lost sale.

The protection period is L+1 days: an order placed on day t arrives on t+L,
and the next order that could cover day t+L+1 is placed on day t+1.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.business_value_config import (
    ANNUAL_HOLDING_RATE,
    DAYS_PER_YEAR,
    ERROR_WINDOW_ORIGINS,
    LEAD_TIME_DAYS,
    MIN_ERROR_SAMPLES,
    SERVICE_QUANTILE,
    UNIT_MARGIN,
    UNIT_VALUE,
)


@dataclass(frozen=True)
class Policy:
    lead_time: int = LEAD_TIME_DAYS
    service_quantile: float = SERVICE_QUANTILE
    error_window: int = ERROR_WINDOW_ORIGINS
    min_error_samples: int = MIN_ERROR_SAMPLES


@dataclass(frozen=True)
class Costs:
    unit_value: float = UNIT_VALUE
    annual_holding_rate: float = ANNUAL_HOLDING_RATE
    unit_margin: float = UNIT_MARGIN

    @property
    def holding_per_unit_day(self) -> float:
        return self.unit_value * self.annual_holding_rate / DAYS_PER_YEAR


def first_decision_day(first_origin: int, policy: Policy) -> int:
    """First day with enough realised forecast errors to size safety stock.

    Origin o's window (days o+1..o+L+1) is realised once day o+L+1 has been
    observed, so it is usable on day t >= o+L+2.
    """
    return first_origin + policy.lead_time + 1 + policy.min_error_samples


def lead_time_forecast_and_actual(demand, forecasts, lead_time):
    """Per origin o: sum F[o,0..L], and the realised sum demand[o+1..o+L+1]."""
    window = lead_time + 1
    fcum = forecasts[:, :window].sum(axis=1)
    csum = np.concatenate([[0.0], np.cumsum(demand, dtype=float)])
    n = len(demand)
    acum = np.full(n, np.nan)
    o = np.arange(n - window)
    acum[o] = csum[o + 1 + window] - csum[o + 1]
    return fcum, acum


def simulate(
    demand: np.ndarray,
    forecasts: np.ndarray,
    first_origin: int,
    policy: Policy = Policy(),
    costs: Costs = Costs(),
    *,
    first_day: int | None = None,
) -> pd.DataFrame:
    """Replay days first_day..N-1 and return one row per day."""
    demand = np.asarray(demand, dtype=float)
    n = len(demand)
    L, window = policy.lead_time, policy.lead_time + 1
    if forecasts.shape[1] < window:
        raise ValueError("forecast horizon shorter than lead time + 1")
    t0 = first_decision_day(first_origin, policy) if first_day is None else first_day

    fcum_all = forecasts[:, :window].sum(axis=1)
    csum = np.concatenate([[0.0], np.cumsum(demand, dtype=float)])

    on_hand = 0.0
    arrivals = np.zeros(n + L + 2)
    rows = []

    for t in range(t0, n):
        # 1. receive orders due today
        on_hand += arrivals[t]

        # 2a. safety ratio from forecasts whose whole window is already known.
        #     newest usable origin: o + L + 2 <= t   ->   o <= t - L - 2
        newest = t - L - 2
        lo = max(first_origin, newest - policy.error_window + 1)
        if newest >= lo:
            o = np.arange(lo, newest + 1)
            actual = csum[o + 1 + window] - csum[o + 1]   # highest index used: t
            fc = fcum_all[o]
            ok = fc > 1e-9
            sample = actual[ok] / fc[ok]
        else:
            sample = np.empty(0)
        if len(sample) >= policy.min_error_samples:
            ratio_q = float(np.quantile(sample, policy.service_quantile, method="higher"))
        else:
            ratio_q = 1.0

        # 2b. order-up-to level and order
        forecast_cum = fcum_all[t - 1]            # forecast made at end of day t-1
        target = max(0.0, forecast_cum * ratio_q)
        position = on_hand + arrivals[t + 1 : t + L + 1].sum()   # on hand + on order
        order = float(np.ceil(target - position)) if target > position else 0.0
        if t == t0 and on_hand == 0.0 and order > 0:
            on_hand = order                        # start fully stocked
            order = 0.0
        arrivals[t + L] += order

        # 3. today's demand is revealed
        d = demand[t]
        sold = min(on_hand, d)
        lost = d - sold
        on_hand -= sold
        rows.append((t, d, sold, lost, on_hand, order, target, forecast_cum, ratio_q))

    out = pd.DataFrame(
        rows,
        columns=[
            "day", "demand", "sold", "lost", "on_hand_end",
            "order_qty", "order_up_to", "lead_time_forecast", "safety_ratio",
        ],
    )
    out["stockout"] = out["lost"] > 0
    return out


def summarise(log: pd.DataFrame, costs: Costs = Costs(), mask: np.ndarray | None = None) -> dict:
    """The four business metrics (+ context) for a (sub)set of days."""
    sub = log if mask is None else log[mask]
    holding = float(sub["on_hand_end"].sum() * costs.holding_per_unit_day)
    lost_units = float(sub["lost"].sum())
    demand = float(sub["demand"].sum())
    return {
        "days": int(len(sub)),
        "stockout_days": int(sub["stockout"].sum()),
        "lost_units": lost_units,
        "avg_inventory": float(sub["on_hand_end"].mean()),
        "holding_cost": holding,
        "fill_rate": 1.0 - lost_units / demand if demand > 0 else float("nan"),
        "lost_margin": lost_units * costs.unit_margin,
        "total_cost": holding + lost_units * costs.unit_margin,
    }