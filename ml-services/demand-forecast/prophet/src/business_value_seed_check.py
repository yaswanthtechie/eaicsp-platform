"""Robustness: repeat the low-volume tiers with different thinning seeds.

    python -m src.business_value_seed_check
"""

import numpy as np
import pandas as pd

from src.business_value_config import (
    LEAD_TIME_DAYS, REPORT_DIR, THINNING_SEED, VOLUME_TIERS,
)
from src.business_value_simulation import (
    equal_fill_rate_table, get_forecasts, run_tier,
)
from src.multi_horizon_data import load_daily_data
from src.walk_forward_forecasts import load_ensemble_weights

SEEDS = (1, 2, 3)
TIERS = ("medium movers (~30/day)", "slow movers (~5/day)")


def main() -> None:
    daily = load_daily_data()
    dates = pd.DatetimeIndex(daily["date"])
    y = daily["quantity_sold"].to_numpy(dtype=float)
    weights = load_ensemble_weights()
    out = []
    for tier in TIERS:
        p = VOLUME_TIERS[tier] / y.mean()
        for s in SEEDS:
            rng = np.random.default_rng(THINNING_SEED + 1000 * s)
            yt = rng.binomial(y.astype(np.int64), p).astype(float)
            name = f"{tier}__seed{s}"
            f = get_forecasts(name, dates, yt, weights, refresh=False)
            _, frontier, _, _ = run_tier(name, dates, yt, f, (LEAD_TIME_DAYS,))
            eq = equal_fill_rate_table(pd.DataFrame(frontier))
            eq["tier"], eq["seed"] = tier, s
            out.append(eq)
    pd.concat(out).to_csv(REPORT_DIR / "seed_robustness.csv", index=False)


if __name__ == "__main__":
    main()