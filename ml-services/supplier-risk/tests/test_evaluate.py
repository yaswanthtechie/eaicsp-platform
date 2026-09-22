"""
Tests for Supplier Risk Evaluation: Fixed Thresholds, Non-Circular Validation,
Independently Authored Labels, and Classification Metrics.
"""

import json
from pathlib import Path
import pytest

from src.config import (
    DEFAULT_TIER_LOW_CEILING,
    DEFAULT_TIER_MEDIUM_CEILING,
    DEFAULT_TIER_HIGH_CEILING,
    TIER_BOUNDARIES,
    Settings,
    get_settings,
)
from src.evaluate import (
    assign_risk_tier,
    load_validation_dataset,
    evaluate_dataset,
    evaluate_held_out_validation,
    HUMAN_BENCHMARK_EXPECTATIONS,
    VALID_TIERS,
)


# ------------------------------------------------------------------
# 1. Fixed Configuration Values & Independence Tests
# ------------------------------------------------------------------

def test_tier_thresholds_are_fixed_configuration_values():
    """
    Verify tier boundaries are explicit, deterministic configuration constants
    defined in src/config.py a priori, before evaluation.
    """
    # 1. Check default constants exist and have expected ordering
    assert DEFAULT_TIER_LOW_CEILING == 60.0
    assert DEFAULT_TIER_MEDIUM_CEILING == 72.0
    assert DEFAULT_TIER_HIGH_CEILING == 85.0
    assert DEFAULT_TIER_LOW_CEILING < DEFAULT_TIER_MEDIUM_CEILING < DEFAULT_TIER_HIGH_CEILING

    # 2. Check TIER_BOUNDARIES map
    assert TIER_BOUNDARIES["Low"] == 60.0
    assert TIER_BOUNDARIES["Medium"] == 72.0
    assert TIER_BOUNDARIES["High"] == 85.0

    # 3. Check Settings instance defaults
    cfg = get_settings()
    assert cfg.tier_low_ceiling == 60.0
    assert cfg.tier_medium_ceiling == 72.0
    assert cfg.tier_high_ceiling == 85.0

    # 4. Settings to_dict serialization contains tier ceilings
    d = cfg.to_dict()
    assert d["tier_low_ceiling"] == 60.0
    assert d["tier_medium_ceiling"] == 72.0
    assert d["tier_high_ceiling"] == 85.0


def test_thresholds_not_derived_from_predictions():
    """
    Verify assign_risk_tier maps raw score strictly according to fixed config
    ceilings, without dependency on prediction outputs, company names, or headline counts.
    """
    cfg = Settings(tier_low_ceiling=60.0, tier_medium_ceiling=72.0, tier_high_ceiling=85.0)

    # Low band: score < 60.0
    assert assign_risk_tier(0.0, config=cfg) == "Low"
    assert assign_risk_tier(35.5, config=cfg) == "Low"
    assert assign_risk_tier(59.99, config=cfg) == "Low"

    # Medium band: 60.0 <= score < 72.0
    assert assign_risk_tier(60.00, config=cfg) == "Medium"
    assert assign_risk_tier(65.50, config=cfg) == "Medium"
    assert assign_risk_tier(71.99, config=cfg) == "Medium"

    # High band: 72.0 <= score < 85.0
    assert assign_risk_tier(72.00, config=cfg) == "High"
    assert assign_risk_tier(78.50, config=cfg) == "High"
    assert assign_risk_tier(84.99, config=cfg) == "High"

    # Critical band: score >= 85.0
    assert assign_risk_tier(85.00, config=cfg) == "Critical"
    assert assign_risk_tier(92.40, config=cfg) == "Critical"
    assert assign_risk_tier(100.0, config=cfg) == "Critical"


def test_custom_threshold_injection_alters_classification_deterministically():
    """
    Verify tier classification adapts deterministically when initialized with
    different configuration settings, proving thresholds are configurable.
    """
    custom_cfg = Settings(
        tier_low_ceiling=40.0,
        tier_medium_ceiling=65.0,
        tier_high_ceiling=80.0,
    )
    # Score 50.0 is Medium under custom_cfg (< 65.0), but would be Low under default (< 60.0)
    assert assign_risk_tier(50.0, config=custom_cfg) == "Medium"
    assert assign_risk_tier(50.0) == "Low"


# ------------------------------------------------------------------
# 2. Held-Out Validation Dataset Integrity & Ground Truth Independence
# ------------------------------------------------------------------

def test_held_out_dataset_loads_correctly():
    """
    Verify held-out synthetic validation dataset file exists, parses correctly,
    and contains required fields in every record.
    """
    dataset = load_validation_dataset()
    assert isinstance(dataset, list)
    assert len(dataset) == 96, f"Expected 96 headlines, got {len(dataset)}"

    valid_tiers = {"Low", "Medium", "High", "Critical"}
    for idx, record in enumerate(dataset):
        assert "supplier" in record, f"Record {idx} missing 'supplier'"
        assert "headline" in record, f"Record {idx} missing 'headline'"
        assert "expected_tier" in record, f"Record {idx} missing 'expected_tier'"
        assert "rationale" in record, f"Record {idx} missing 'rationale'"

        assert isinstance(record["supplier"], str) and record["supplier"].strip()
        assert isinstance(record["headline"], str) and record["headline"].strip()
        assert record["expected_tier"] in valid_tiers
        assert isinstance(record["rationale"], str) and record["rationale"].strip()


def test_expected_tiers_exist_independently_of_model_scores():
    """
    Verify ground truth expected tiers are static JSON fields authored
    independently from any model scoring logic.
    """
    json_path = Path(__file__).parent.parent / "src" / "synthetic_held_out_validation.json"
    assert json_path.exists(), "Held-out validation JSON file must exist"

    # Read raw JSON directly without running any model logic
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Check each supplier has consistent expected tier and 8 headlines
    supplier_tiers = {}
    supplier_counts = {}
    for item in data:
        s = item["supplier"]
        t = item["expected_tier"]
        supplier_counts[s] = supplier_counts.get(s, 0) + 1
        if s in supplier_tiers:
            assert supplier_tiers[s] == t, f"Inconsistent expected tier for supplier {s}"
        else:
            supplier_tiers[s] = t

    # 12 suppliers total, exactly 8 headlines each
    assert len(supplier_tiers) == 12
    for s, count in supplier_counts.items():
        assert count == 8, f"{s} expected 8 headlines, got {count}"

    # Verify balanced representation: 3 suppliers per tier
    tier_distribution = {}
    for t in supplier_tiers.values():
        tier_distribution[t] = tier_distribution.get(t, 0) + 1

    assert tier_distribution == {"Low": 3, "Medium": 3, "High": 3, "Critical": 3}


def test_development_and_held_out_datasets_are_distinct():
    """
    Verify complete disjointness between the 15-company development benchmark
    and the held-out validation dataset:
    - Zero overlapping supplier names.
    - Zero overlapping headline texts.
    """
    val_dataset = load_validation_dataset()
    val_suppliers = set(d["supplier"] for d in val_dataset)
    val_headlines = set(d["headline"] for d in val_dataset)

    dev_suppliers = set(HUMAN_BENCHMARK_EXPECTATIONS.keys())

    # Check supplier names: completely disjoint
    overlap = dev_suppliers.intersection(val_suppliers)
    assert len(overlap) == 0, f"Datasets must be disjoint, found overlapping suppliers: {overlap}"

    # Load 15-company dev headlines and check text disjointness
    dev_path = Path(__file__).parent.parent / "src" / "supplier_headlines_15.json"
    with open(dev_path, "r", encoding="utf-8") as f:
        dev_data = json.load(f)
    dev_headlines = set(d["headline"] for d in dev_data)

    headline_overlap = dev_headlines.intersection(val_headlines)
    assert len(headline_overlap) == 0, f"Found overlapping headline text: {headline_overlap}"


# ------------------------------------------------------------------
# 3. Held-Out Evaluation Metrics, Confusion Matrix & Per-Tier Results
# ------------------------------------------------------------------

def test_evaluate_held_out_validation_metrics_and_structure():
    """
    Verify evaluate_held_out_validation executes cleanly, reports all required
    metrics, produces a valid confusion matrix, and reports per-tier metrics.
    """
    results = evaluate_held_out_validation()

    # Core structure
    assert results["dataset_type"] == "SYNTHETIC_HELD_OUT_VALIDATION"
    assert results["total_suppliers"] == 12
    assert results["total_headlines"] == 96
    assert results["disjoint_from_development"] is True
    assert isinstance(results["matches"], int)
    assert 0 <= results["matches"] <= 12
    assert 0.0 <= results["accuracy"] <= 1.0
    assert results["accuracy_percentage"] == round(results["accuracy"] * 100.0, 2)

    # Per-tier metrics validation
    per_tier = results["per_tier_metrics"]
    for tier in VALID_TIERS:
        assert tier in per_tier
        stats = per_tier[tier]
        assert "support" in stats
        assert "predicted" in stats
        assert "true_positives" in stats
        assert "precision" in stats
        assert "recall" in stats
        assert "f1" in stats

        assert stats["support"] == 3  # Balanced 3 suppliers per tier
        assert stats["predicted"] >= 0
        assert stats["true_positives"] >= 0
        assert 0.0 <= stats["precision"] <= 1.0
        assert 0.0 <= stats["recall"] <= 1.0
        assert 0.0 <= stats["f1"] <= 1.0

    # Confusion matrix validation
    cm = results["confusion_matrix"]
    total_matrix_sum = 0
    for exp_tier in VALID_TIERS:
        assert exp_tier in cm
        row_sum = 0
        for pred_tier in VALID_TIERS:
            assert pred_tier in cm[exp_tier]
            val = cm[exp_tier][pred_tier]
            assert isinstance(val, int) and val >= 0
            row_sum += val
        # Row sum must equal ground truth support
        assert row_sum == per_tier[exp_tier]["support"]
        total_matrix_sum += row_sum

    assert total_matrix_sum == 12

    # Company reports
    assert len(results["company_reports"]) == 12
    for report in results["company_reports"]:
        assert "supplier" in report
        assert "headline_count" in report
        assert report["headline_count"] == 8
        assert "risk_score" in report
        assert "confidence" in report
        assert "expected_tier" in report
        assert "model_tier" in report
        assert "match_status" in report
        assert report["match_status"] in {"MATCH", "MISMATCH"}
        assert "rationale" in report


def test_evaluate_held_out_validation_determinism():
    """
    Verify evaluation produces strictly deterministic metrics across multiple invocations.
    """
    run_1 = evaluate_held_out_validation()
    run_2 = evaluate_held_out_validation()

    assert run_1["total_suppliers"] == run_2["total_suppliers"]
    assert run_1["matches"] == run_2["matches"]
    assert run_1["accuracy"] == run_2["accuracy"]
    assert run_1["confusion_matrix"] == run_2["confusion_matrix"]
    assert run_1["per_tier_metrics"] == run_2["per_tier_metrics"]


# ------------------------------------------------------------------
# 4. Error Handling & Validation Failure Paths
# ------------------------------------------------------------------

def test_load_validation_dataset_missing_file_raises():
    """Missing validation dataset file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="not found"):
        load_validation_dataset("non_existent_file_12345.json")


def test_load_validation_dataset_invalid_record_raises(tmp_path):
    """Dataset with missing required keys raises ValueError."""
    bad_data = [{"supplier": "Test Supplier", "headline": "A headline"}]  # Missing expected_tier
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(json.dumps(bad_data), encoding="utf-8")

    with pytest.raises(ValueError, match="missing required key: 'expected_tier'"):
        load_validation_dataset(str(bad_file))


def test_load_validation_dataset_invalid_tier_raises(tmp_path):
    """Dataset with unrecognized expected tier raises ValueError."""
    bad_data = [
        {
            "supplier": "Test Supplier",
            "headline": "A headline",
            "expected_tier": "ExtremelyDangerous",
        }
    ]
    bad_file = tmp_path / "bad_tier.json"
    bad_file.write_text(json.dumps(bad_data), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid expected_tier"):
        load_validation_dataset(str(bad_file))
