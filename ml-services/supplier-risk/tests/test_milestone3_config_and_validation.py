"""
Tests for Milestone 3: Config Inspection, Configuration Validation Failure Paths,
15-Company Dataset Integrity, and Benchmark Evaluation.
"""

import json
import pytest
from fastapi.testclient import TestClient

from src.analyze import app
from src.config import (
    Settings,
    validate_numeric_weight,
    validate_signal_weights,
    validate_aggregation_strategy,
    validate_aggregation_top_k,
    get_settings,
)
from src.data import (
    load_headlines,
    load_15_company_dataset,
    load_15_company_trend_dataset,
)
from src.evaluate import evaluate_dataset, assign_risk_tier
from src.trend import validate_date


client = TestClient(app)


# ------------------------------------------------------------------
# 1. Config Endpoint Tests
# ------------------------------------------------------------------

def test_get_config_endpoint_success():
    """Verify GET /api/v1/supplier-risk/config returns 200 with full schema."""
    response = client.get("/api/v1/supplier-risk/config")
    assert response.status_code == 200
    data = response.json()

    assert "model_name" in data
    assert "negative_sentiment_penalty" in data
    assert "neutral_sentiment_penalty" in data
    assert "positive_sentiment_penalty" in data
    assert "max_risk_score" in data
    assert "confidence_divisor" in data
    assert "aggregation_strategy" in data
    assert "aggregation_top_k" in data
    assert "recency_half_life_days" in data
    assert "signal_weights" in data

    assert isinstance(data["signal_weights"], dict)
    assert len(data["signal_weights"]) >= 10
    assert "bankruptcy" in data["signal_weights"]
    assert data["signal_weights"]["bankruptcy"] == 50
    assert data["aggregation_strategy"] in {"top_k_mean", "max", "blend", "mean"}
    assert data["recency_half_life_days"] > 0


def test_predict_endpoint_does_not_require_custom_weights():
    """Ensure POST /predict operates strictly from server-side config without overrides."""
    payload = {
        "supplier_name": "Siemens",
        "headlines": [
            "Siemens secures multi-billion dollar railway electrification deal."
        ],
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "supplier_summary" in data
    assert "Siemens" in data["supplier_summary"]


# ------------------------------------------------------------------
# 2. Configuration Validation Failure Paths
# ------------------------------------------------------------------

def test_validate_numeric_weight_negative_fails():
    """Negative weight must raise ValueError."""
    with pytest.raises(ValueError, match="cannot be negative"):
        validate_numeric_weight("test_weight", -10.0)


def test_validate_numeric_weight_non_numeric_fails():
    """Non-numeric weight must raise ValueError."""
    with pytest.raises(ValueError, match="must be numeric"):
        validate_numeric_weight("test_weight", "ten")


def test_validate_numeric_weight_boolean_fails():
    """Boolean weight must raise ValueError (bool is subclass of int in Python)."""
    with pytest.raises(ValueError, match="must be numeric"):
        validate_numeric_weight("test_weight", True)


def test_validate_numeric_weight_zero_disallowed():
    """When allow_zero=False, 0 must raise ValueError."""
    with pytest.raises(ValueError, match="must be greater than zero"):
        validate_numeric_weight("test_divisor", 0, allow_zero=False)


def test_validate_signal_weights_non_dict_fails():
    """Non-dictionary signal weights must raise ValueError."""
    with pytest.raises(ValueError, match="must be a dictionary"):
        validate_signal_weights(["not", "a", "dict"])


def test_validate_signal_weights_empty_keyword_fails():
    """Empty or whitespace-only keyword must raise ValueError."""
    with pytest.raises(ValueError, match="non-empty string"):
        validate_signal_weights({"": 20})

    with pytest.raises(ValueError, match="non-empty string"):
        validate_signal_weights({"   ": 20})


def test_validate_signal_weights_negative_value_fails():
    """Negative weight inside dictionary must raise ValueError."""
    with pytest.raises(ValueError, match="cannot be negative"):
        validate_signal_weights({"strike": -15})


def test_validate_aggregation_strategy_invalid():
    """Invalid aggregation strategy must raise ValueError."""
    with pytest.raises(ValueError, match="Invalid aggregation strategy"):
        validate_aggregation_strategy("unsupported_strategy")


def test_validate_aggregation_strategy_non_string():
    """Non-string aggregation strategy must raise ValueError."""
    with pytest.raises(ValueError, match="must be a string"):
        validate_aggregation_strategy(123)


def test_validate_aggregation_top_k_invalid():
    """Non-positive or invalid top-k must raise ValueError."""
    with pytest.raises(ValueError, match="must be greater than zero"):
        validate_aggregation_top_k(0)

    with pytest.raises(ValueError, match="must be greater than zero"):
        validate_aggregation_top_k(-3)

    with pytest.raises(ValueError, match="must be an integer"):
        validate_aggregation_top_k("invalid_int")


def test_settings_malformed_json_env(monkeypatch):
    """Settings initialized with malformed SIGNAL_WEIGHTS_JSON must raise ValueError."""
    monkeypatch.setenv("SIGNAL_WEIGHTS_JSON", "{invalid-json")
    with pytest.raises(ValueError, match="Invalid SIGNAL_WEIGHTS_JSON"):
        Settings()


# ------------------------------------------------------------------
# 3. 15-Company Dataset Integrity Tests
# ------------------------------------------------------------------

def test_15_company_dataset_integrity():
    """Verify 15-company dataset has 15 suppliers, 12 headlines each, 180 total."""
    dataset = load_15_company_dataset()
    assert len(dataset) == 15, f"Expected 15 suppliers, got {len(dataset)}"

    total_headlines = 0
    expected_suppliers = {
        "Boeing", "Intel", "Tesla", "Nissan", "Foxconn",
        "TSMC", "Maersk", "BASF", "Siemens", "Apex Logistics",
        "ASML", "Glencore", "Lockheed Martin", "Evergreen Marine", "Northvolt",
    }
    assert set(dataset.keys()) == expected_suppliers

    for supplier, headlines in dataset.items():
        assert len(headlines) == 12, f"{supplier} expected 12 headlines, got {len(headlines)}"
        for h in headlines:
            assert isinstance(h, str) and h.strip()
            total_headlines += 1

    assert total_headlines == 180


def test_15_company_trend_dataset_integrity():
    """Verify 15-company trend dataset has 15 suppliers, 12 date-aware records each."""
    trend_data = load_15_company_trend_dataset()
    assert len(trend_data) == 15

    for supplier, records in trend_data.items():
        assert len(records) == 12
        for rec in records:
            assert "date" in rec
            assert "headline" in rec
            validate_date(rec["date"])  # Validates YYYY-MM-DD


# ------------------------------------------------------------------
# 4. Standalone Evaluation & Tier Determination Tests
# ------------------------------------------------------------------

def test_assign_risk_tier():
    """Verify calibrated 4-tier operational reporting categorization thresholds."""
    assert assign_risk_tier(10.0) == "Low"
    assert assign_risk_tier(56.33) == "Low"
    assert assign_risk_tier(59.9) == "Low"
    assert assign_risk_tier(60.0) == "Medium"
    assert assign_risk_tier(68.35) == "Medium"
    assert assign_risk_tier(71.9) == "Medium"
    assert assign_risk_tier(72.0) == "High"
    assert assign_risk_tier(78.33) == "High"
    assert assign_risk_tier(84.9) == "High"
    assert assign_risk_tier(85.0) == "Critical"
    assert assign_risk_tier(90.47) == "Critical"
    assert assign_risk_tier(100.0) == "Critical"


def test_evaluate_dataset_structure():
    """Verify evaluate_dataset returns required keys and valid company reports."""
    results = evaluate_dataset()
    assert "company_reports" in results
    assert "total_evaluated" in results
    assert "matches" in results
    assert "spread" in results
    assert "std_dev" in results
    assert "tier_counts" in results
    assert "distribution_explanation" in results

    assert results["total_evaluated"] == 15
    assert len(results["company_reports"]) == 15

    # Calibrated reporting guarantees
    assert results["matches"] >= 12, f"Expected >= 12 human matches, got {results['matches']}"
    for tier in ["Low", "Medium", "High", "Critical"]:
        assert results["tier_counts"][tier] > 0, f"Expected tier '{tier}' to be populated"

    for report in results["company_reports"]:
        assert "supplier" in report
        assert "headline_count" in report
        assert "risk_score" in report
        assert "confidence" in report
        assert "top_signals" in report
        assert "human_expected_tier" in report
        assert "model_tier" in report
        assert "match_status" in report
        assert report["match_status"] in {"MATCH", "MISMATCH"}
        assert "reason" in report


def test_baseline_dataset_preservation():
    """Verify original 10-company dataset loader remains intact and operational."""
    baseline = load_headlines()
    assert len(baseline) == 10
    assert "Apex Logistics" in baseline
    assert "Boeing" in baseline
