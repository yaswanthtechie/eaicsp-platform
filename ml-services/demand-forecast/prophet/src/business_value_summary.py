"""Plain-English summary of the business backtest, generated from the result CSVs.

Run after the simulation:   python -m src.business_value_summary
Writes reports/business_value/summary.md. Every number is read from
equal_fill_rate.csv and assumptions.json, so it can never drift from the results.
"""

from __future__ import annotations

import json

import pandas as pd

from src.business_value_config import LEAD_TIME_DAYS, REPORT_DIR, TARGET_FILL_RATE

SMALL_GAIN = 0.10          # saving < 10% of stock vs the best naive = "doesn't really help"
ENSEMBLE_EDGE = 0.02       # ensemble must beat the best single model by >= 2% to "pay off"
MODELS = ("prophet", "xgboost")
NAIVES = ("naive_weekly", "naive_ma28")
NICE = {
    "ensemble": "the ensemble", "ensemble_50_50": "the 50/50 ensemble",
    "prophet": "Prophet alone", "xgboost": "XGBoost alone",
    "naive_weekly": "'same day last week'", "naive_ma28": "a 28-day average",
}


def tier_verdicts(equal: pd.DataFrame) -> pd.DataFrame:
    """One row per tier: stock each approach needs at the target fill rate, and the verdict."""
    e = equal[(equal.lead_time == LEAD_TIME_DAYS) & equal.avg_inventory_needed.notna()]
    rows = []
    for tier, g in e.groupby("tier", sort=False):
        stock = g.set_index("approach")["avg_inventory_needed"]
        cost = g.set_index("approach")["holding_cost_over_window"]
        best_naive = stock[list(NAIVES)].idxmin()
        best_model = stock[list(MODELS)].idxmin()
        saving = 1 - stock["ensemble"] / stock[best_naive]
        edge = 1 - stock["ensemble"] / stock[best_model]
        if saving < SMALL_GAIN:
            verdict = f"little or no gain: saves only {saving:.0%} of stock vs {NICE[best_naive]}"
        elif edge < ENSEMBLE_EDGE:
            verdict = f"forecasting helps, but the ensemble adds nothing over {NICE[best_model]}"
        else:
            verdict = "the ensemble pays off"
        rows.append({
            "tier": tier, "ensemble_stock": stock["ensemble"],
            "best_naive": best_naive, "best_naive_stock": stock[best_naive],
            "saving_vs_naive": saving,
            "money_saved_over_window": cost[best_naive] - cost["ensemble"],
            "best_single_model": best_model, "ensemble_edge_vs_best_model": edge,
            "verdict": verdict,
        })
    return pd.DataFrame(rows)


def build_summary(equal: pd.DataFrame, assumptions: dict) -> str:
    v = tier_verdicts(equal)
    days = int(equal.loc[equal.lead_time == LEAD_TIME_DAYS, "window_days"].iloc[0])
    lines = [
        "# Does a better forecast save money? (generated from the CSVs)",
        "",
        f"Question: to keep {TARGET_FILL_RATE:.0%} of demand in stock, how much stock does each "
        f"forecast make us hold? Replayed day by day over {days} days, {LEAD_TIME_DAYS}-day supplier "
        "lead time, no future data used.",
        "",
        "| Volume tier | Stock needed: ensemble | Best naive (stock) | Stock saved | "
        f"Holding cost saved over {days} days | Verdict |",
        "|---|---|---|---|---|---|",
    ]
    for r in v.itertuples(index=False):
        lines.append(
            f"| {r.tier} | {r.ensemble_stock:,.1f} | {NICE[r.best_naive]} ({r.best_naive_stock:,.1f}) "
            f"| {r.saving_vs_naive:.0%} | {r.money_saved_over_window:,.0f} | {r.verdict} |"
        )
    helps = v[v.verdict == "the ensemble pays off"].tier.tolist()
    lines += ["", "## In plain English", "",
              "- The ensemble pays off for: " + (", ".join(helps) if helps else "no tier") + "."]
    for r in v[v.verdict != "the ensemble pays off"].itertuples(index=False):
        lines.append(f"- {r.tier}: {r.verdict}.")
    lines += [
        "", "## Read this before quoting the numbers", "",
        f"- Money is an estimate: unit value {assumptions['unit_value']} (assumed, the data has no "
        f"prices), holding cost {assumptions['annual_holding_rate']:.0%} of value per year.",
        f"- Volume tiers: {assumptions.get('volume_tiers', 'see assumptions.json')}.",
        f"- Ensemble weights: {assumptions.get('ensemble_weighting', 'see assumptions.json')}.",
        "- 'Stock saved' compares approaches at the SAME fill rate. At a fixed safety setting "
        "(metrics_headline.csv) approaches land on different fill rates, so their stockout days "
        "are not directly comparable.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    equal = pd.read_csv(REPORT_DIR / "equal_fill_rate.csv")
    assumptions = json.loads((REPORT_DIR / "assumptions.json").read_text())
    out = REPORT_DIR / "summary.md"
    out.write_text(build_summary(equal, assumptions), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()