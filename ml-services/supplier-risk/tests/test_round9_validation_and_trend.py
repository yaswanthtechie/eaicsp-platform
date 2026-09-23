"""
Unit and integration tests for Round 9 Supplier Risk NLP:
1. Historical Supplier Risk Trend & Deterioration Detection
2. Compliance Integration Contract Documentation Integrity
3. 25-Company Benchmark and Trend Dataset Validation
4. Positive, Negative, Duplicate, and Outdated/Relevant Scenario Validations
"""

import json
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from src.analyze import app
from src.config import Settings, get_settings
from src.data import (
    load_25_company_dataset,
    load_25_company_trend_dataset,
    load_active_trend_headlines,
    load_headlines,
)
from src.evaluate import (
    evaluate_25_company_benchmark,
    HUMAN_BENCHMARK_EXPECTATIONS,
    load_validation_dataset,
)
from src.trend import (
    calculate_supplier_trend,
    detect_deteriorating_suppliers,
    validate_date,
)


@pytest.fixture(autouse=True)
def mock_sentiment():
    """Mock FinBERT sentiment for fast unit testing."""
    with patch("src.predict.analyze_sentiment") as mock:
        def side_effect(text):
            lower = text.lower()
            if any(w in lower for w in [
                "bankruptcy", "fraud", "strike", "lawsuit", "sanction",
                "disruption", "recall", "layoff", "default", "insolvency",
                "downgrade", "shutdown", "outage", "cyberattack", "investigation"
            ]):
                return {"label": "negative", "confidence": 0.98}
            if any(w in lower for w in ["positive", "record", "profit", "growth", "secures", "expands", "award"]):
                return {"label": "positive", "confidence": 0.95}
            return {"label": "neutral", "confidence": 0.95}

        mock.side_effect = side_effect
        yield mock


# ------------------------------------------------------------------
# 1. 25-Company Benchmark & Trend Dataset Integrity Tests
# ------------------------------------------------------------------

def test_25_company_dataset_loading_and_counts():
    """Verify 25-company dataset contains exactly 25 suppliers and 300 headlines."""
    dataset = load_25_company_dataset()
    assert len(dataset) == 25, f"Expected 25 companies, got {len(dataset)}"
    
    total_headlines = sum(len(headlines) for headlines in dataset.values())
    assert total_headlines == 300, f"Expected 300 headlines, got {total_headlines}"
    
    for supplier, headlines in dataset.items():
        assert len(headlines) == 12, f"{supplier} expected 12 headlines, got {len(headlines)}"
        for hl in headlines:
            assert isinstance(hl, str) and hl.strip(), f"Empty headline found for {supplier}"


def test_25_company_trend_dataset_loading_and_dates():
    """Verify 25-company trend dataset contains exactly 25 suppliers, 12 records each, with valid dates."""
    trend_data = load_25_company_trend_dataset()
    assert len(trend_data) == 25, f"Expected 25 suppliers, got {len(trend_data)}"

    for supplier, records in trend_data.items():
        assert len(records) == 12, f"{supplier} expected 12 records, got {len(records)}"
        for r in records:
            assert "date" in r and "headline" in r
            validated = validate_date(r["date"])
            assert validated == r["date"]
            assert isinstance(r["headline"], str) and r["headline"].strip()


def test_active_trend_headlines_prefers_25_company_dataset():
    """Verify load_active_trend_headlines returns the 25-company trend dataset."""
    active = load_active_trend_headlines()
    assert len(active) == 25
    assert "Schneider Electric" in active
    assert "Texas Instruments" in active
    assert "Apex Logistics" in active


def test_baseline_dataset_preservation_unbroken():
    """Ensure Round 5 baseline 10-company loader is completely preserved and untouched."""
    baseline = load_headlines()
    assert len(baseline) == 10
    assert "Boeing" in baseline
    assert "Apex Logistics" in baseline


def test_25_companies_disjoint_from_held_out_validation():
    """Verify 25 benchmark companies have zero overlap with 12 held-out validation entities."""
    h25_dataset = load_25_company_dataset()
    val_dataset = load_validation_dataset()
    
    h25_suppliers = set(h25_dataset.keys())
    val_suppliers = set(d["supplier"] for d in val_dataset)
    
    overlap = h25_suppliers.intersection(val_suppliers)
    assert len(overlap) == 0, f"Benchmark and held-out validation must be disjoint! Found overlap: {overlap}"


# ------------------------------------------------------------------
# 2. Historical Risk Trend & Deterioration Detection Tests
# ------------------------------------------------------------------

def test_trend_deterioration_flag_when_risk_rises():
    """Verify a supplier with worsening risk is flagged with is_deteriorating: True."""
    records = [
        # Previous window (30-60 days ago): clean news
        {"date": "2026-01-15", "headline": "Alpha Logistics reports record quarterly revenue growth."},
        {"date": "2026-01-25", "headline": "Alpha Logistics signs positive expansion deal in Europe."},
        # Current window (last 30 days): acute risk events
        {"date": "2026-03-05", "headline": "Alpha Logistics suffers cyberattack compromising shipping records."},
        {"date": "2026-03-20", "headline": "Alpha Logistics faces fraud investigation and debt default."},
    ]

    res = calculate_supplier_trend("Alpha Logistics", records)
    assert res["previous_risk_score"] is not None
    assert res["current_risk_score"] > res["previous_risk_score"]
    assert res["trend_direction"] == "rising"
    assert res["is_deteriorating"] is True
    assert res["risk_delta"] is not None
    assert res["risk_delta"] > 0
    assert "Risk is deteriorating" in res["deterioration_summary"]


def test_trend_deterioration_flag_when_risk_improves():
    """Verify a supplier recovering from distress has is_deteriorating: False and falling direction."""
    records = [
        # Previous window: severe risk events
        {"date": "2026-01-15", "headline": "Beta Corp hit with bankruptcy and severe insolvency fears."},
        {"date": "2026-01-25", "headline": "Beta Corp faces major labor strike shutting down assembly."},
        # Current window: recovery and clean operations
        {"date": "2026-03-05", "headline": "Beta Corp successfully concludes restructuring and resolves dispute."},
        {"date": "2026-03-20", "headline": "Beta Corp reports record positive earnings and new client contracts."},
    ]

    res = calculate_supplier_trend("Beta Corp", records)
    assert res["previous_risk_score"] is not None
    assert res["current_risk_score"] < res["previous_risk_score"]
    assert res["trend_direction"] == "falling"
    assert res["is_deteriorating"] is False
    assert res["risk_delta"] is not None
    assert res["risk_delta"] < 0
    assert "Risk is improving" in res["deterioration_summary"]


def test_trend_deterioration_flag_when_risk_stable():
    """Verify a supplier with steady risk has is_deteriorating: False and stable direction."""
    records = [
        {"date": "2026-01-15", "headline": "Gamma Corp holds routine annual shareholder meeting."},
        {"date": "2026-01-25", "headline": "Gamma Corp issues standard quarterly operational report."},
        {"date": "2026-03-05", "headline": "Gamma Corp maintains normal manufacturing operations."},
        {"date": "2026-03-20", "headline": "Gamma Corp conducts routine facility safety inspection."},
    ]

    res = calculate_supplier_trend("Gamma Corp", records)
    assert res["trend_direction"] == "stable"
    assert res["is_deteriorating"] is False
    assert res["risk_delta"] is not None
    assert abs(res["risk_delta"]) <= 3.0
    assert "Risk is stable" in res["deterioration_summary"]


def test_trend_deterioration_flag_when_no_history():
    """Verify is_deteriorating is False and risk_delta is None when no historical window exists."""
    records = [
        {"date": "2026-03-20", "headline": "Delta Corp faces production disruption due to parts shortage."},
    ]

    res = calculate_supplier_trend("Delta Corp", records)
    assert res["previous_risk_score"] is None
    assert res["risk_delta"] is None
    assert res["is_deteriorating"] is False
    assert "Insufficient historical data" in res["deterioration_summary"]


def test_detect_deteriorating_suppliers_multi_entity():
    """Verify detect_deteriorating_suppliers isolates deteriorating entities and ranks by delta."""
    records = [
        # Supplier 1: Deteriorating (clean past, acute bad now)
        {"supplier": "WorseningSupplier", "date": "2026-01-15", "headline": "WorseningSupplier reports positive earnings."},
        {"supplier": "WorseningSupplier", "date": "2026-03-20", "headline": "WorseningSupplier hit with fraud and debt default."},

        # Supplier 2: Improving (bad past, clean now)
        {"supplier": "ImprovingSupplier", "date": "2026-01-15", "headline": "ImprovingSupplier faces bankruptcy and default."},
        {"supplier": "ImprovingSupplier", "date": "2026-03-20", "headline": "ImprovingSupplier reports record positive earnings."},

        # Supplier 3: Stable (clean throughout)
        {"supplier": "StableSupplier", "date": "2026-01-15", "headline": "StableSupplier holds shareholder meeting."},
        {"supplier": "StableSupplier", "date": "2026-03-20", "headline": "StableSupplier conducts standard inspection."},
    ]

    deteriorating_list = detect_deteriorating_suppliers(records)
    assert len(deteriorating_list) == 1
    assert deteriorating_list[0]["supplier"] == "WorseningSupplier"
    assert deteriorating_list[0]["is_deteriorating"] is True
    assert deteriorating_list[0]["risk_delta"] > 0
    assert len(deteriorating_list[0]["top_evidence"]) > 0


# ------------------------------------------------------------------
# 3. Scenario-Specific Validations
# ------------------------------------------------------------------

def test_scenario_positive_articles_mitigate_risk():
    """Verify mitigating positive articles reduce supplier risk score."""
    negative_only = [
        {"date": "2026-03-10", "headline": "Acme Corp faces supply disruption delaying shipments."},
    ]
    mitigated_positive = [
        {"date": "2026-03-10", "headline": "Acme Corp faces supply disruption delaying shipments."},
        {"date": "2026-03-12", "headline": "Acme Corp reports record positive profit and expansion."},
        {"date": "2026-03-15", "headline": "Acme Corp secures multi-million dollar positive contract."},
    ]

    res_neg = calculate_supplier_trend("Acme Corp", negative_only)
    res_mit = calculate_supplier_trend("Acme Corp", mitigated_positive)

    assert res_mit["current_risk_score"] < res_neg["current_risk_score"], (
        f"Expected mitigated score ({res_mit['current_risk_score']}) < negative score ({res_neg['current_risk_score']})"
    )


def test_scenario_acute_negative_articles_severity():
    """Verify acute negative signals drive elevated risk scores and high/critical classifications."""
    acute_records = [
        {"date": "2026-03-10", "headline": "DistressedCorp files for bankruptcy following massive debt default."},
        {"date": "2026-03-15", "headline": "Regulators launch criminal fraud investigation into DistressedCorp."},
    ]

    res = calculate_supplier_trend("DistressedCorp", acute_records)
    assert res["current_risk_score"] >= 80.0
    assert len(res["top_evidence"]) > 0
    signals = [s["keyword"] for item in res["top_evidence"] for s in item.get("signals", [])]
    assert any(k in signals for k in ["bankruptcy", "default", "fraud"])


def test_scenario_duplicate_articles_deduplication():
    """Verify duplicate articles do not artificially inflate headline counts or confidence."""
    headline = "SupplierX faces investigation over accounting irregularities."
    unique_records = [
        {"date": "2026-03-10", "headline": headline},
    ]
    duplicate_records = [
        {"date": "2026-03-10", "headline": headline},
        {"date": "2026-03-10", "headline": headline},
        {"date": "2026-03-10", "headline": f"  {headline}  "},
    ]

    res_unique = calculate_supplier_trend("SupplierX", unique_records)
    res_dup = calculate_supplier_trend("SupplierX", duplicate_records)

    assert res_dup["article_count"] == 1
    assert res_dup["current_risk_score"] == res_unique["current_risk_score"]
    assert res_dup["overall_confidence"] == res_unique["overall_confidence"]


def test_scenario_outdated_articles_excluded_from_current_window():
    """Verify articles older than trend_window_days do not affect current_risk_score."""
    # Reference date: 2026-03-31
    # Article 1: 2026-01-10 (80 days ago, outdated) -> Bankruptcy
    # Article 2: 2026-03-31 (today, current window) -> Positive earnings
    records = [
        {"date": "2026-01-10", "headline": "OldCorp files for bankruptcy after massive fraud."},
        {"date": "2026-03-31", "headline": "OldCorp reports positive earnings and strong profit."},
    ]

    res = calculate_supplier_trend("OldCorp", records)
    assert res["article_count"] == 2
    assert res["current_window_article_count"] == 1
    assert res["historical_article_count"] == 1
    # Current window score must only reflect the positive headline (0.0), NOT the old bankruptcy headline
    assert res["current_risk_score"] == 0.0
    assert res["previous_risk_score"] is not None
    assert res["previous_risk_score"] > 80.0
    assert res["trend_direction"] == "falling"
    assert res["is_deteriorating"] is False


# ------------------------------------------------------------------
# 4. Compliance Integration Contract Documentation Integrity Test
# ------------------------------------------------------------------

def test_compliance_contract_documentation_exists():
    """Verify COMPLIANCE_INTEGRATION_CONTRACT.md exists and contains all required specifications."""
    contract_path = (
        Path(__file__).resolve().parent.parent / "COMPLIANCE_INTEGRATION_CONTRACT.md"
    )
    assert contract_path.exists(), "COMPLIANCE_INTEGRATION_CONTRACT.md must exist"

    content = contract_path.read_text(encoding="utf-8")

    # Verify key structural components
    assert "FUTURE WORK" in content or "future work" in content
    assert "NO RUNTIME HTTP" in content or "NO RUNTIME" in content
    assert "OFAC" in content and "UN" in content and "EU" in content
    assert "Unified Risk Decision Matrix" in content
    assert "is_deteriorating" in content
    assert "Circuit Breaking" in content or "circuit breaker" in content
    assert "Fallbacks" in content or "Graceful Service Degradation" in content


# ------------------------------------------------------------------
# 5. 25-Company Benchmark Evaluation Function Tests
# ------------------------------------------------------------------

def test_evaluate_25_company_benchmark_structure():
    """Verify evaluate_25_company_benchmark returns full schema and passes scenario checks."""
    res = evaluate_25_company_benchmark()
    assert res["total_evaluated"] == 25
    assert len(res["company_reports"]) == 25
    assert res["spread"] >= 40.0
    assert res["std_dev"] > 10.0
    assert "scenario_checks" in res
    assert res["scenario_checks"]["all_25_suppliers_present"] is True
    assert res["scenario_checks"]["critical_suppliers_high_risk"] is True
    assert res["scenario_checks"]["low_suppliers_controlled_risk"] is True


# ------------------------------------------------------------------
# 6. API Endpoint Contract Serialization Tests
# ------------------------------------------------------------------

def test_api_trend_response_includes_deterioration_fields():
    """Verify Trend API response schema includes is_deteriorating, risk_delta, and deterioration_summary."""
    with TestClient(app) as client:
        payload = {
            "supplier_name": "Tesla",
            "articles": [
                {"date": "2026-01-15", "headline": "Tesla reports record positive earnings."},
                {"date": "2026-03-20", "headline": "Tesla announces major recall of 2 million vehicles."},
            ],
        }
        response = client.post("/api/v1/supplier-risk/trend", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert "is_deteriorating" in data
        assert isinstance(data["is_deteriorating"], bool)
        assert "risk_delta" in data
        assert "deterioration_summary" in data
        assert "trend_direction" in data
        assert "top_evidence" in data
        assert "overall_confidence" in data
