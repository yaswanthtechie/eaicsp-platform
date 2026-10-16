
"""Robustness: repeat the low-volume tiers with different thinning seeds.

Run:
    python -m src.business_value_seed_check
    python -m src.business_value_seed_check --refresh
"""

import argparse

import numpy as np
import pandas as pd

from src.business_value_config import (
    LEAD_TIME_DAYS,
    REPORT_DIR,
    THINNING_SEED,
    VOLUME_TIERS,
)
from src.business_value_simulation import (
    equal_fill_rate_table,
    get_forecasts,
    run_tier,
)
from src.multi_horizon_data import load_daily_data

SEEDS = (1, 2, 3)
TIERS = ("medium movers (~30/day)", "slow movers (~5/day)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--refresh",
        action="store_true",
        help="refit models, ignore cache",
    )
    args = ap.parse_args()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    daily = load_daily_data()
    dates = pd.DatetimeIndex(daily["date"])
    y = daily["quantity_sold"].to_numpy(dtype=float)

    out = []

    for tier in TIERS:
        p = VOLUME_TIERS[tier] / y.mean()

        for s in SEEDS:
            rng = np.random.default_rng(THINNING_SEED + 1000 * s)
            yt = rng.binomial(y.astype(np.int64), p).astype(float)
            name = f"{tier}__seed{s}"

            print(f"tier: {name}", flush=True)

            f = get_forecasts(
                name,
                dates,
                yt,
                refresh=args.refresh,
            )

            _, frontier, _, _ = run_tier(
                name,
                dates,
                yt,
                f,
                (LEAD_TIME_DAYS,),
            )

            eq = equal_fill_rate_table(pd.DataFrame(frontier))
            eq["tier"] = tier
            eq["seed"] = s
            out.append(eq)

    result = pd.concat(out, ignore_index=True)
    output_path = REPORT_DIR / "seed_robustness.csv"
    result.to_csv(output_path, index=False)

    print(f"wrote {output_path}", flush=True)


if __name__ == "__main__":
    main()
