"""Chart: stock needed to reach the target fill rate, relative to the weekly-naive forecast."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.business_value_config import LEAD_TIME_DAYS, REPORT_DIR, TARGET_FILL_RATE

ORDER = ["ensemble", "prophet", "xgboost", "naive_ma28"]
LABEL = {
    "ensemble": "Ensemble",
    "prophet": "Prophet",
    "xgboost": "XGBoost",
    "naive_ma28": "Naive: 28-day average",
}
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#8a8985"]  # three model colours + grey for the naive


def main() -> None:
    e = pd.read_csv(REPORT_DIR / "equal_fill_rate.csv")
    e = e[e.lead_time == LEAD_TIME_DAYS]
    p = e.pivot(index="tier", columns="approach", values="avg_inventory_needed")
    tiers = list(p.index)
    rel = p[ORDER].div(p["naive_weekly"], axis=0) * 100   # weekly naive = 100

    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=150)
    width = 0.2
    x = np.arange(len(tiers))
    for i, a in enumerate(ORDER):
        bars = ax.bar(x + (i - 1.5) * width, rel[a], width - 0.02, color=COLORS[i], label=LABEL[a])
        for b, v in zip(bars, rel[a]):
            ax.text(b.get_x() + b.get_width() / 2, v + 1, f"{v:.0f}",
                    ha="center", fontsize=8, color="#0b0b0b")

    ax.axhline(100, color="#52514e", lw=1, ls="--")
    ax.text(len(tiers) - 0.45, 101.5, "Naive: same weekday last week = 100",
            ha="right", fontsize=8.5, color="#52514e")
    ax.set_xticks(x)
    ax.set_xticklabels([t.replace(" (", "\n(") for t in tiers], fontsize=9)
    ax.set_ylabel("Average stock needed (weekly-naive = 100)")
    ax.set_ylim(0, 112)
    ax.set_title(
        f"Stock needed to fill {TARGET_FILL_RATE:.0%} of demand, {LEAD_TIME_DAYS}-day lead time\n(lower is better)",
        fontsize=11, loc="left",
    )
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", color="#e5e4df", lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.13), fontsize=9)
    fig.tight_layout()
    fig.savefig(REPORT_DIR / "stock_needed.png")


if __name__ == "__main__":
    main()