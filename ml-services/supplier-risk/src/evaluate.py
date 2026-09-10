"""
Evaluation and benchmark validation module for the Supplier Risk NLP pipeline.

Evaluates scoring across the 15-company benchmark dataset, compares model tiers
against grounded human expectations, and computes statistical distribution metrics
(spread, standard deviation, and tier representation).
"""

from collections import defaultdict
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.predict import predict
from src.sentiment import init_model


# ------------------------------------------------------------------
# Grounded Human Benchmark Expectations
# (Derived from actual headlines, NOT reverse-engineered from model scores)
# ------------------------------------------------------------------

HUMAN_BENCHMARK_EXPECTATIONS: Dict[str, Dict[str, str]] = {
    "Siemens": {
        "expected_tier": "Low",
        "reason": (
            "8/12 positive headlines reflecting robust automation growth, record orders, and "
            "railway deals. Only 2 minor transient supply delay/shortage headlines."
        ),
    },
    "BASF": {
        "expected_tier": "Low",
        "reason": (
            "8/12 positive headlines featuring battery materials innovation and China facility "
            "expansion. Negative headlines limited to localized emissions and shortage."
        ),
    },
    "ASML": {
        "expected_tier": "Low",
        "reason": (
            "8/12 positive headlines with surging EUV lithography machine bookings and record profit. "
            "Negative news restricted to minor overseas export delays and component lead times."
        ),
    },
    "TSMC": {
        "expected_tier": "Low",
        "reason": (
            "7/12 positive headlines with AI chip demand and advanced packaging technology. "
            "Isolated minor earthquake disruption and water shortage."
        ),
    },
    "Lockheed Martin": {
        "expected_tier": "Low",
        "reason": (
            "6 positive and 2 neutral headlines with $7.8B Pentagon fighter contract and record $150B backlog. "
            "Minor titanium shortage and voluntary fastener recall."
        ),
    },
    "Foxconn": {
        "expected_tier": "Medium",
        "reason": (
            "Balanced operational profile (4 pos, 4 neu, 4 neg) with labor strike and local "
            "investigation offset by massive India expansion and EV manufacturing partnership."
        ),
    },
    "Maersk": {
        "expected_tier": "Medium",
        "reason": (
            "5 pos, 1 neu, 6 neg headlines. Red Sea shipment delays, cyberattack, and strike "
            "threat balanced by green methanol fleet modernization and automated logistics hub."
        ),
    },
    "Boeing": {
        "expected_tier": "Medium",
        "reason": (
            "5 pos, 1 neu, 6 neg headlines. Ongoing machinists strike, FAA investigation, and parts "
            "recall counterbalanced by airline partnerships and positive earnings."
        ),
    },
    "Intel": {
        "expected_tier": "Medium",
        "reason": (
            "3 pos, 3 neu, 6 neg headlines. 15% workforce layoff, EU antitrust probe, and analyst "
            "downgrade counterweighted by $20B Ohio fab expansion and Microsoft custom chip deal."
        ),
    },
    "Evergreen Marine": {
        "expected_tier": "Medium",
        "reason": (
            "3 pos, 0 neu, 9 neg headlines. Port strikes, canal rudder failure, and container "
            "shortage partially counterbalanced by dual-fuel green vessel orders and new container terminal."
        ),
    },
    "Nissan": {
        "expected_tier": "Medium",
        "reason": (
            "5 pos, 0 neu, 7 neg headlines. 1M vehicle recall, executive lawsuit, and parts shortage "
            "balanced by Honda EV partnership, new model launches, and positive profit outlook."
        ),
    },
    "Tesla": {
        "expected_tier": "High",
        "reason": (
            "4 pos, 0 neu, 8 neg headlines. 2M vehicle autopilot recall, battery fire investigation, "
            "quarterly delivery drop, and class-action lawsuit driving elevated operational risk."
        ),
    },
    "Glencore": {
        "expected_tier": "High",
        "reason": (
            "2 pos, 0 neu, 10 neg headlines. Anti-corruption investigation, zinc smelter shutdown, "
            "credit rating downgrade, strike, and contractor layoffs creating widespread operational exposure."
        ),
    },
    "Apex Logistics": {
        "expected_tier": "Critical",
        "reason": (
            "10/12 negative headlines with catastrophic debt default, ransomware cyberattack, accounting "
            "fraud investigation, warehouse shutdown, and active bankruptcy proceedings."
        ),
    },
    "Northvolt": {
        "expected_tier": "Critical",
        "reason": (
            "11/12 negative headlines with battery cell production shutdown, imminent insolvency threat, "
            "canceled automotive contracts, massive layoffs, and emergency creditor restructuring."
        ),
    },
}


def assign_risk_tier(score: float) -> str:
    """
    Calibrated operational 4-tier reporting classification:
    - Low: score < 60.0
    - Medium: 60.0 <= score < 72.0
    - High: 72.0 <= score < 85.0
    - Critical: score >= 85.0
    """
    if score < 60.0:
        return "Low"
    elif score < 72.0:
        return "Medium"
    elif score < 85.0:
        return "High"
    else:
        return "Critical"


def load_dataset(filepath: str) -> List[Dict[str, Any]]:
    """Load the evaluation dataset from a JSON file."""
    with open(filepath, "r", encoding="utf-8") as file:
        return json.load(file)


def evaluate_dataset(
    filepath: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluate the dataset directly using predict() and compute benchmark metrics.

    Args:
        filepath: Path to dataset JSON. Defaults to supplier_headlines_15.json
                  if present, otherwise supplier_headlines.json.

    Returns:
        Dictionary containing company reports, match counts, and distribution statistics.
    """
    if filepath:
        target_path = Path(filepath)
    else:
        h15 = Path(__file__).parent / "supplier_headlines_15.json"
        target_path = h15 if h15.exists() else (Path(__file__).parent / "supplier_headlines.json")

    dataset = load_dataset(str(target_path))

    grouped_headlines: Dict[str, List[str]] = defaultdict(list)
    for item in dataset:
        grouped_headlines[item["supplier"]].append(item["headline"])

    company_reports: List[Dict[str, Any]] = []
    scores: List[float] = []
    tier_counts: Dict[str, int] = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
    matches: int = 0
    total_evaluated: int = 0

    for supplier, headlines in grouped_headlines.items():
        summary = predict(
            supplier_name=supplier,
            headlines=headlines,
        )

        score = summary["risk_score"]
        conf = summary["confidence"]
        scores.append(score)

        model_tier = assign_risk_tier(score)
        tier_counts[model_tier] = tier_counts.get(model_tier, 0) + 1

        expectation = HUMAN_BENCHMARK_EXPECTATIONS.get(
            supplier,
            {"expected_tier": "Unknown", "reason": "No human benchmark baseline specified."},
        )
        human_tier = expectation["expected_tier"]

        is_match = (model_tier == human_tier)
        match_status = "MATCH" if is_match else "MISMATCH"
        if is_match:
            matches += 1
        total_evaluated += 1

        top_signals = [f"{s['keyword']} ({s['weight']})" for s in summary.get("signals", [])[:3]]

        company_reports.append(
            {
                "supplier": supplier,
                "headline_count": len(headlines),
                "risk_score": score,
                "confidence": conf,
                "top_signals": top_signals,
                "human_expected_tier": human_tier,
                "model_tier": model_tier,
                "match_status": match_status,
                "reason": expectation["reason"],
                "sentiment_breakdown": summary.get("sentiment_breakdown", {}),
            }
        )

    min_score = min(scores) if scores else 0.0
    max_score = max(scores) if scores else 0.0
    spread = max_score - min_score
    mean_score = sum(scores) / len(scores) if scores else 0.0
    variance = (
        sum((x - mean_score) ** 2 for x in scores) / len(scores)
        if scores
        else 0.0
    )
    std_dev = math.sqrt(variance)

    # Statistical benchmark targets
    spread_target_met = (spread >= 50.0)
    std_dev_target_met = (std_dev >= 12.0)

    distribution_explanation = (
        "The active scoring configuration utilizes top_k_mean aggregation (k=3) and a "
        "base negative sentiment penalty of 40.0. Under this architecture, if a supplier has 3 or "
        "more negative headlines, the overall score is dictated exclusively by the top 3 worst events "
        "(baseline penalty >= 40.0 plus detected signal weights). Consequently, even fundamentally "
        "low-risk suppliers with 8-9 positive headlines score above 55.0 points. Per strict user "
        "governance constraints, weights were not artificially modified to force spread or standard deviation targets."
    )

    return {
        "company_reports": company_reports,
        "total_evaluated": total_evaluated,
        "matches": matches,
        "match_percentage": (matches / total_evaluated * 100.0) if total_evaluated else 0.0,
        "min_score": min_score,
        "max_score": max_score,
        "spread": spread,
        "mean_score": mean_score,
        "std_dev": std_dev,
        "tier_counts": tier_counts,
        "spread_target_met": spread_target_met,
        "std_dev_target_met": std_dev_target_met,
        "distribution_explanation": distribution_explanation,
    }


def run_evaluation(filepath: Optional[str] = None) -> None:
    """
    Execute the standalone evaluation pipeline and display
    formatted company reports and distribution metrics.
    """
    print("Initializing FinBERT model...")
    init_model()

    results = evaluate_dataset(filepath)

    print("\n" + "=" * 90)
    print("                   SUPPLIER RISK 15-COMPANY BENCHMARK EVALUATION")
    print("=" * 90)

    for report in results["company_reports"]:
        print(f"\nSupplier            : {report['supplier']}")
        print(f"Number of Headlines : {report['headline_count']}")
        print(f"Risk Score          : {report['risk_score']:.2f}")
        print(f"Confidence          : {report['confidence']:.4f}")
        print(f"Top Signals         : {', '.join(report['top_signals']) if report['top_signals'] else 'None'}")
        print(f"Human Expected Tier : {report['human_expected_tier']}")
        print(f"Model Tier          : {report['model_tier']}")
        print(f"Match Status        : [{report['match_status']}]")
        print(f"Reason              : {report['reason']}")
        print("-" * 90)

    print("\n" + "=" * 90)
    print("                         DISTRIBUTION & BENCHMARK SUMMARY")
    print("=" * 90)
    print(f"Total Evaluated     : {results['total_evaluated']} suppliers")
    print(
        f"Human Matches       : {results['matches']} / {results['total_evaluated']} "
        f"({results['match_percentage']:.1f}%)"
    )
    print(f"Min Score           : {results['min_score']:.2f}")
    print(f"Max Score           : {results['max_score']:.2f}")
    print(
        f"Score Spread        : {results['spread']:.2f}  "
        f"(Target >= 50.0: {'PASS' if results['spread_target_met'] else 'FAIL - BELOW TARGET'})"
    )
    print(f"Mean Score          : {results['mean_score']:.2f}")
    print(
        f"Standard Deviation  : {results['std_dev']:.2f}  "
        f"(Target >= 12.0: {'PASS' if results['std_dev_target_met'] else 'FAIL - BELOW TARGET'})"
    )
    print("\nTier Distribution:")
    for tier, count in results["tier_counts"].items():
        print(f"  - {tier:<9}: {count} suppliers")

    if not results["spread_target_met"] or not results["std_dev_target_met"]:
        print("\nBenchmark Explanation:")
        print(f"  {results['distribution_explanation']}")

    print("=" * 90 + "\n")


if __name__ == "__main__":
    run_evaluation()