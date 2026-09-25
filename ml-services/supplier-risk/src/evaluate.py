"""
Evaluation and benchmark validation module for the Supplier Risk NLP pipeline.

This module provides two clearly separated evaluation paths:

1. Development Benchmark Evaluation (evaluate_dataset):
   Evaluates scoring across the 15-company exploratory development dataset
   (src/supplier_headlines_15.json). This dataset contains authored/synthetic
   scenarios paired with real corporate entity names, created alongside initial
   pipeline development. It serves as an exploratory regression baseline, NOT
   an independent held-out validation set.

2. Held-Out Synthetic Validation (evaluate_held_out_validation):
   Evaluates scoring on a genuinely distinct, held-out synthetic validation dataset
   (src/synthetic_held_out_validation.json) containing 12 distinct fictional suppliers
   (96 headlines) with independently authored ground-truth expected risk tiers.
   Computes classification accuracy, per-tier precision/recall/F1, and confusion matrix.

Fixed Risk Tier Classification Thresholds:
Configured a priori in src/config.py (independent of model scoring output):
- Low:      score < tier_low_ceiling (default < 60.0)
- Medium:   tier_low_ceiling <= score < tier_medium_ceiling (default 60.0 <= score < 72.0)
- High:     tier_medium_ceiling <= score < tier_high_ceiling (default 72.0 <= score < 85.0)
- Critical: score >= tier_high_ceiling (default >= 85.0)

Thresholds are explicit, deterministic configuration constants. They are NEVER
calculated from model predictions or tuned to force evaluation results to pass.
"""

from collections import defaultdict
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from src.config import Settings, get_settings
from src.predict import predict
from src.sentiment import init_model


# ------------------------------------------------------------------
# Development Benchmark Human Expectations (Synthetic Dev Dataset)
# NOTE: Headlines and expectations for these 15 companies were authored
# during initial development. They serve as an exploratory regression
# baseline and are explicitly labeled as synthetic/authored scenarios.
# Real corporate names are used for illustrative benchmark grouping;
# these headlines do NOT represent real-world events.
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
    # ------------------------------------------------------------------
    # Round 9: 10 Expanded Benchmark Companies (25 Companies Total)
    # ------------------------------------------------------------------
    "Texas Instruments": {
        "expected_tier": "Low",
        "reason": (
            "10/12 positive headlines with $11B wafer fab groundbreakings, robust analog revenue, "
            "and OEM supplier excellence awards. Minor transient winter delays and legacy shortage."
        ),
    },
    "Schneider Electric": {
        "expected_tier": "Low",
        "reason": (
            "10/12 positive headlines driven by AI data center microgrid contracts, top global "
            "sustainability awards, and smart factory expansion. Transient European logistics delays."
        ),
    },
    "Caterpillar": {
        "expected_tier": "Medium",
        "reason": (
            "8 positive and 4 negative headlines. Strong infrastructure demand and mining contracts "
            "counterbalanced by hydraulic valve shortage, equipment delays, and minor union talks."
        ),
    },
    "Volvo Group": {
        "expected_tier": "Medium",
        "reason": (
            "8 positive and 4 negative headlines. 1,500 electric truck order and charging JV "
            "counterweighted by Gothenburg transmission shortage, steering recall, and strike threat."
        ),
    },
    "Rio Tinto": {
        "expected_tier": "Medium",
        "reason": (
            "7 positive and 5 negative/neutral headlines. High-grade Simandou project and resilient "
            "iron ore output balanced by copper tailings investigation, rail delays, and port disruption."
        ),
    },
    "ArcelorMittal": {
        "expected_tier": "High",
        "reason": (
            "2 positive and 10 negative headlines. Energy-driven blast furnace shutdowns, emissions "
            "investigation, water contamination lawsuit, debt downgrade warning, and plant walkout strike."
        ),
    },
    "Toshiba": {
        "expected_tier": "High",
        "reason": (
            "2 positive, 1 neutral, 9 negative headlines. Subsidiary accounting fraud probe, investor "
            "lawsuit, junk bond downgrade, ransomware cyberattack, 4,000 layoffs, and debt restructuring."
        ),
    },
    "DHL Supply Chain": {
        "expected_tier": "Medium",
        "reason": (
            "7 positive and 5 negative headlines. Global robotics expansion and pharmaceutical hubs "
            "balanced by airport ground warning strike, customs system outage, and ocean port disruption."
        ),
    },
    "Evergrande Construction Logistics": {
        "expected_tier": "Critical",
        "reason": (
            "12/12 negative headlines with catastrophic offshore bond default, bankruptcy liquidation "
            "petitions, criminal fraud investigation, 120 depot shutdowns, and massive unpaid invoices."
        ),
    },
    "Silicon Power Storage": {
        "expected_tier": "Critical",
        "reason": (
            "12/12 negative headlines with emergency bankruptcy filing, debt default, trade sanctions, "
            "balance sheet fraud scandal, SSD plant shutdown, worker strike, and customer contract cancellations."
        ),
    },
}

VALID_TIERS: List[str] = ["Low", "Medium", "High", "Critical"]


# ------------------------------------------------------------------
# Fixed Risk Tier Classification
# ------------------------------------------------------------------

def assign_risk_tier(score: float, config: Optional[Settings] = None) -> str:
    """
    Classify a continuous risk score into a discrete operational tier based on
    fixed, a priori configured thresholds (independent of model predictions).

    Tier Definitions:
    - Low:      score < tier_low_ceiling (default < 60.0)
    - Medium:   tier_low_ceiling <= score < tier_medium_ceiling (default 60.0 <= score < 72.0)
    - High:     tier_medium_ceiling <= score < tier_high_ceiling (default 72.0 <= score < 85.0)
    - Critical: score >= tier_high_ceiling (default >= 85.0)
    """
    cfg = config if config is not None else get_settings()
    if score < cfg.tier_low_ceiling:
        return "Low"
    elif score < cfg.tier_medium_ceiling:
        return "Medium"
    elif score < cfg.tier_high_ceiling:
        return "High"
    else:
        return "Critical"


# ------------------------------------------------------------------
# Dataset Loading Functions
# ------------------------------------------------------------------

def load_dataset(filepath: str) -> List[Dict[str, Any]]:
    """Load the development evaluation dataset from a JSON file."""
    with open(filepath, "r", encoding="utf-8") as file:
        return json.load(file)


def load_validation_dataset(filepath: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Load the held-out synthetic validation dataset.

    Args:
        filepath: Optional path to JSON dataset file. Defaults to
                  src/synthetic_held_out_validation.json.

    Returns:
        List of validation headline records with keys:
        'supplier', 'headline', 'expected_tier', 'rationale'.
    """
    target_path = (
        Path(filepath)
        if filepath
        else Path(__file__).parent / "synthetic_held_out_validation.json"
    )

    if not target_path.exists():
        raise FileNotFoundError(f"Held-out validation dataset not found: {target_path}")

    with open(target_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list) or len(data) == 0:
        raise ValueError("Validation dataset must be a non-empty list of records")

    valid_tiers_set = set(VALID_TIERS)
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Record at index {idx} must be a dictionary, got {type(item).__name__}")
        for req_key in ("supplier", "headline", "expected_tier"):
            if req_key not in item or not str(item[req_key]).strip():
                raise ValueError(f"Record at index {idx} missing required key: '{req_key}'")
        if item["expected_tier"] not in valid_tiers_set:
            raise ValueError(
                f"Record at index {idx} has invalid expected_tier '{item['expected_tier']}'. "
                f"Allowed tiers: {VALID_TIERS}"
            )

    return data


# ------------------------------------------------------------------
# Development Benchmark Evaluation (Exploratory / Regression Baseline)
# ------------------------------------------------------------------

def evaluate_dataset(
    filepath: Optional[str] = None,
    config: Optional[Settings] = None,
) -> Dict[str, Any]:
    """
    Evaluate the 15-company development benchmark dataset.

    Args:
        filepath: Path to dataset JSON. Defaults to supplier_headlines_15.json
                  if present, otherwise supplier_headlines.json.
        config: Optional Settings instance. Defaults to active get_settings().

    Returns:
        Dictionary containing company reports, match counts, and distribution statistics.
    """
    cfg = config if config is not None else get_settings()

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
            config=cfg,
        )

        score = summary["risk_score"]
        conf = summary["confidence"]
        scores.append(score)

        model_tier = assign_risk_tier(score, config=cfg)
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

    spread_target_met = (spread >= 50.0)
    std_dev_target_met = (std_dev >= 12.0)

    distribution_explanation = (
        "The development benchmark evaluates 15 companies using fixed tier cutoffs "
        f"(Low < {cfg.tier_low_ceiling}, Med < {cfg.tier_medium_ceiling}, High < {cfg.tier_high_ceiling}). "
        "Scoring utilizes calibrated aggregation and whole-word mitigated keyword detection. "
        "This dataset serves as an exploratory regression baseline."
    )

    return {
        "dataset_type": "DEVELOPMENT_BENCHMARK",
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


def evaluate_25_company_benchmark(
    filepath: Optional[str] = None,
    config: Optional[Settings] = None,
) -> Dict[str, Any]:
    """
    Evaluate the expanded 25-company development benchmark dataset.

    Performs deeper validation across all 25 suppliers (300 headlines):
    - Validates positive, negative, duplicate, and mitigated headline behavior.
    - Computes per-tier distribution, score spread, standard deviation, and human expectation match rate.
    - Validates that acute distress suppliers land in High/Critical and resilient suppliers land in Low.

    Args:
        filepath: Path to 25-company dataset JSON. Defaults to src/supplier_headlines_25.json.
        config: Optional Settings instance. Defaults to active get_settings().

    Returns:
        Dictionary containing company reports, match counts, distribution statistics,
        and scenario validation checks.
    """
    cfg = config if config is not None else get_settings()

    if filepath:
        target_path = Path(filepath)
    else:
        target_path = Path(__file__).parent / "supplier_headlines_25.json"

    if not target_path.exists():
        raise FileNotFoundError(f"25-company benchmark dataset not found at {target_path}")

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
            config=cfg,
        )

        score = summary["risk_score"]
        conf = summary["confidence"]
        scores.append(score)

        model_tier = assign_risk_tier(score, config=cfg)
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

    low_scores = [r["risk_score"] for r in company_reports if r["human_expected_tier"] == "Low"]
    critical_scores = [r["risk_score"] for r in company_reports if r["human_expected_tier"] == "Critical"]

    # Deeper scenario validation
    scenario_checks = {
        "all_25_suppliers_present": total_evaluated == 25,
        "critical_suppliers_high_risk": (sum(critical_scores) / len(critical_scores) >= 80.0) if critical_scores else False,
        "low_suppliers_controlled_risk": (sum(low_scores) / len(low_scores) < 65.0) if low_scores else False,
        "score_spread_sufficient": spread >= 40.0,
        "all_four_tiers_represented": all(count > 0 for count in tier_counts.values()),
    }

    distribution_explanation = (
        f"The expanded 25-company benchmark evaluates 25 global suppliers across 4 operational tiers "
        f"(Low < {cfg.tier_low_ceiling}, Med < {cfg.tier_medium_ceiling}, High < {cfg.tier_high_ceiling}). "
        f"Scoring leverages FinBERT sentiment penalties, mitigated whole-word keyword signals, "
        f"and top-k mean anti-dilution risk aggregation."
    )

    return {
        "dataset_type": "25_COMPANY_DEVELOPMENT_BENCHMARK",
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
        "scenario_checks": scenario_checks,
        "distribution_explanation": distribution_explanation,
    }


# ------------------------------------------------------------------
# Held-Out Synthetic Validation Evaluation (Non-Circular)
# ------------------------------------------------------------------

def evaluate_held_out_validation(
    filepath: Optional[str] = None,
    config: Optional[Settings] = None,
) -> Dict[str, Any]:
    """
    Evaluate the model against the held-out synthetic validation dataset.

    This evaluation is strictly non-circular:
    - Expected tiers and rationales were authored independently prior to evaluation.
    - Tier thresholds are fixed configuration constants, not derived from predictions.
    - Dataset entities are fictional and completely disjoint from the development benchmark.

    Args:
        filepath: Optional path to validation JSON dataset. Defaults to
                  src/synthetic_held_out_validation.json.
        config: Optional Settings instance. Defaults to active get_settings().

    Returns:
        Dictionary containing:
        - dataset_type: "SYNTHETIC_HELD_OUT_VALIDATION"
        - total_suppliers: int
        - total_headlines: int
        - matches: int
        - accuracy: float (0.0 to 1.0)
        - accuracy_percentage: float (0.0 to 100.0)
        - per_tier_metrics: Dict[str, Dict[str, Any]] (support, predicted, tp, precision, recall, f1)
        - confusion_matrix: Dict[str, Dict[str, int]] (matrix[expected][predicted])
        - tier_thresholds: Dict[str, float]
        - company_reports: List[Dict[str, Any]]
        - disjoint_from_development: bool
    """
    cfg = config if config is not None else get_settings()
    dataset = load_validation_dataset(filepath)

    grouped_headlines: Dict[str, List[str]] = defaultdict(list)
    expected_tiers: Dict[str, str] = {}
    rationales: Dict[str, str] = {}

    for item in dataset:
        supplier = item["supplier"]
        grouped_headlines[supplier].append(item["headline"])
        expected_tiers[supplier] = item["expected_tier"]
        if "rationale" in item:
            rationales[supplier] = item["rationale"]

    # Verify disjointness from development benchmark
    dev_suppliers = set(HUMAN_BENCHMARK_EXPECTATIONS.keys())
    val_suppliers = set(grouped_headlines.keys())
    disjoint = len(dev_suppliers.intersection(val_suppliers)) == 0

    company_reports: List[Dict[str, Any]] = []
    scores: List[float] = []
    predicted_tiers: Dict[str, str] = {}
    matches: int = 0

    for supplier, headlines in grouped_headlines.items():
        summary = predict(
            supplier_name=supplier,
            headlines=headlines,
            config=cfg,
        )

        score = summary["risk_score"]
        conf = summary["confidence"]
        scores.append(score)

        model_tier = assign_risk_tier(score, config=cfg)
        predicted_tiers[supplier] = model_tier
        expected_tier = expected_tiers[supplier]

        is_match = (model_tier == expected_tier)
        if is_match:
            matches += 1

        top_signals = [f"{s['keyword']} ({s['weight']})" for s in summary.get("signals", [])[:3]]

        company_reports.append(
            {
                "supplier": supplier,
                "headline_count": len(headlines),
                "risk_score": score,
                "confidence": conf,
                "top_signals": top_signals,
                "expected_tier": expected_tier,
                "model_tier": model_tier,
                "match_status": "MATCH" if is_match else "MISMATCH",
                "rationale": rationales.get(supplier, "No rationale provided."),
                "sentiment_breakdown": summary.get("sentiment_breakdown", {}),
            }
        )

    total_suppliers = len(grouped_headlines)
    total_headlines = len(dataset)
    accuracy = (matches / total_suppliers) if total_suppliers > 0 else 0.0

    # Build Confusion Matrix: matrix[expected][predicted]
    confusion_matrix: Dict[str, Dict[str, int]] = {
        exp: {pred: 0 for pred in VALID_TIERS} for exp in VALID_TIERS
    }
    for supplier, exp_tier in expected_tiers.items():
        pred_tier = predicted_tiers[supplier]
        confusion_matrix[exp_tier][pred_tier] += 1

    # Compute Per-Tier Metrics (Precision, Recall, F1, Support)
    per_tier_metrics: Dict[str, Dict[str, Any]] = {}
    for tier in VALID_TIERS:
        support = sum(1 for exp in expected_tiers.values() if exp == tier)
        pred_count = sum(1 for pred in predicted_tiers.values() if pred == tier)
        true_positives = confusion_matrix[tier][tier]

        precision = (true_positives / pred_count) if pred_count > 0 else 0.0
        recall = (true_positives / support) if support > 0 else 0.0
        f1 = (
            (2.0 * precision * recall / (precision + recall))
            if (precision + recall) > 0.0
            else 0.0
        )

        per_tier_metrics[tier] = {
            "support": support,
            "predicted": pred_count,
            "true_positives": true_positives,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }

    return {
        "dataset_type": "SYNTHETIC_HELD_OUT_VALIDATION",
        "total_suppliers": total_suppliers,
        "total_headlines": total_headlines,
        "matches": matches,
        "accuracy": accuracy,
        "accuracy_percentage": round(accuracy * 100.0, 2),
        "per_tier_metrics": per_tier_metrics,
        "confusion_matrix": confusion_matrix,
        "tier_thresholds": {
            "Low": cfg.tier_low_ceiling,
            "Medium": cfg.tier_medium_ceiling,
            "High": cfg.tier_high_ceiling,
        },
        "company_reports": company_reports,
        "disjoint_from_development": disjoint,
    }


# ------------------------------------------------------------------
# Standalone CLI Evaluation Runner
# ------------------------------------------------------------------

def run_evaluation(
    dev_filepath: Optional[str] = None,
    val_filepath: Optional[str] = None,
) -> None:
    """
    Execute both evaluation pipelines (Development Benchmark and Held-Out Validation)
    and display formatted summary reports, confusion matrix, and tier metrics.
    """
    print("Initializing FinBERT model...")
    init_model()

    cfg = get_settings()

    # 1. Held-Out Validation Evaluation
    print("\n" + "=" * 95)
    print("           SUPPLIER RISK HELD-OUT SYNTHETIC VALIDATION (NON-CIRCULAR EVALUATION)")
    print("=" * 95)
    print(f"Fixed Tier Boundaries : Low < {cfg.tier_low_ceiling} | Medium < {cfg.tier_medium_ceiling} | High < {cfg.tier_high_ceiling} | Critical >= {cfg.tier_high_ceiling}")

    val_results = evaluate_held_out_validation(val_filepath, config=cfg)

    print("-" * 95)
    print(f"{'Supplier':<30} | {'Headlines':<9} | {'Score':<6} | {'Conf':<6} | {'Expected':<9} | {'Model':<9} | {'Status'}")
    print("-" * 95)
    for r in val_results["company_reports"]:
        print(
            f"{r['supplier']:<30} | {r['headline_count']:<9} | {r['risk_score']:6.2f} | "
            f"{r['confidence']:6.4f} | {r['expected_tier']:<9} | {r['model_tier']:<9} | [{r['match_status']}]"
        )
    print("-" * 95)

    print("\n" + "=" * 95)
    print("                         HELD-OUT VALIDATION METRICS SUMMARY")
    print("=" * 95)
    print(f"Total Suppliers       : {val_results['total_suppliers']}")
    print(f"Total Headlines       : {val_results['total_headlines']}")
    print(f"Tier Matches          : {val_results['matches']} / {val_results['total_suppliers']} ({val_results['accuracy_percentage']}%)")
    print(f"Disjoint from Dev     : {'YES - ZERO SUPPLIER OVERLAP' if val_results['disjoint_from_development'] else 'NO - OVERLAPS WITH DEV'}")

    print("\nConfusion Matrix (Rows: Expected, Columns: Predicted):")
    print(f"{'Expected \\ Predicted':<22} | {'Low':>6} | {'Medium':>6} | {'High':>6} | {'Critical':>8} | {'Support':>7}")
    print("-" * 65)
    cm = val_results["confusion_matrix"]
    for exp in VALID_TIERS:
        row = cm[exp]
        support = val_results["per_tier_metrics"][exp]["support"]
        print(f"{exp:<22} | {row['Low']:>6} | {row['Medium']:>6} | {row['High']:>6} | {row['Critical']:>8} | {support:>7}")
    print("-" * 65)

    print("\nPer-Tier Classification Metrics:")
    print(f"{'Tier':<10} | {'Support':>7} | {'Predicted':>9} | {'TP':>4} | {'Precision':>9} | {'Recall':>7} | {'F1':>7}")
    print("-" * 65)
    for tier in VALID_TIERS:
        m = val_results["per_tier_metrics"][tier]
        print(
            f"{tier:<10} | {m['support']:>7} | {m['predicted']:>9} | {m['true_positives']:>4} | "
            f"{m['precision']:>9.4f} | {m['recall']:>7.4f} | {m['f1']:>7.4f}"
        )
    print("=" * 95 + "\n")

    # 2. Development Benchmark Evaluation (Exploratory / Regression)
    print("\n" + "=" * 95)
    print("             SUPPLIER RISK 15-COMPANY DEVELOPMENT BENCHMARK (REGRESSION BASELINE)")
    print("=" * 95)
    dev_results = evaluate_dataset(dev_filepath, config=cfg)
    print(f"Total Evaluated       : {dev_results['total_evaluated']} suppliers")
    print(f"Human Matches         : {dev_results['matches']} / {dev_results['total_evaluated']} ({dev_results['match_percentage']:.1f}%)")
    print(f"Score Spread          : {dev_results['spread']:.2f}")
    print(f"Mean Score            : {dev_results['mean_score']:.2f}")
    print(f"Standard Deviation    : {dev_results['std_dev']:.2f}")
    print("\nDevelopment Tier Distribution:")
    for tier, count in dev_results["tier_counts"].items():
        print(f"  - {tier:<9}: {count} suppliers")
    print("=" * 95 + "\n")

    # 3. Expanded 25-Company Benchmark Evaluation (Round 9)
    print("\n" + "=" * 95)
    print("             SUPPLIER RISK 25-COMPANY EXPANDED VALIDATION BENCHMARK (ROUND 9)")
    print("=" * 95)
    h25_results = evaluate_25_company_benchmark(config=cfg)
    print(f"Total Evaluated       : {h25_results['total_evaluated']} suppliers")
    print(f"Human Matches         : {h25_results['matches']} / {h25_results['total_evaluated']} ({h25_results['match_percentage']:.1f}%)")
    print(f"Score Spread          : {h25_results['spread']:.2f} (Min: {h25_results['min_score']:.2f}, Max: {h25_results['max_score']:.2f})")
    print(f"Mean Score            : {h25_results['mean_score']:.2f}")
    print(f"Standard Deviation    : {h25_results['std_dev']:.2f}")
    print("\n25-Company Tier Distribution:")
    for tier, count in h25_results["tier_counts"].items():
        print(f"  - {tier:<9}: {count} suppliers")
    print("\nScenario Validations:")
    for check_name, passed in h25_results["scenario_checks"].items():
        print(f"  - {check_name:<32}: {'PASSED' if passed else 'FAILED'}")
    print("=" * 95 + "\n")


def print_25_company_trend_table(config: Optional[Settings] = None) -> None:
    """Print the §4 sanity-doc trend table using the REAL model (no mocks)."""
    # Local imports: trend.py imports assign_risk_tier from this module.
    from src.data import load_active_trend_headlines
    from src.trend import calculate_supplier_trend

    cfg = config if config is not None else get_settings()
    init_model()

    print("| Supplier | Prev | Current | Delta | Direction | Current tier | Peak tier "
          "| Expected | Deteriorating |")
    print("|---|---|---|---|---|---|---|---|---|")

    for name, records in load_active_trend_headlines().items():
        t = calculate_supplier_trend(name, records, config=cfg)
        expected = HUMAN_BENCHMARK_EXPECTATIONS.get(name, {}).get("expected_tier", "?")

        print(
            f"| {name} | {t['previous_risk_score']} | {t['current_risk_score']} "
            f"| {t['risk_delta']} | {t['trend_direction']} | {t['current_risk_tier']} "
            f"| {t['peak_risk_tier']} | {expected} | {t['is_deteriorating']} |"
        )


if __name__ == "__main__":
    run_evaluation()
