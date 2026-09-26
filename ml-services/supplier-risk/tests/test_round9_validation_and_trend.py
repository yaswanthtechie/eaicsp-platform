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

from src.analyze import app, TrendAnalysisRequest, TrendResponse
from src.config import Settings, get_settings
from src.data import (
    load_25_company_dataset,
    load_25_company_trend_dataset,
    load_active_trend_headlines,
    load_headlines,
)
from src.evaluate import (
    assign_risk_tier,
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
# 4. Compliance Integration Contract Documentation & Schema Integrity Tests
# ------------------------------------------------------------------

def test_compliance_contract_documentation_and_real_interface():
    """
    Must Fix #3: Verify COMPLIANCE_INTEGRATION_CONTRACT.md exists, references Geethika's
    real compliance service interface (ComplianceRequest, ComplianceResponse, is_flagged,
    MATCH_THRESHOLD), and contains no invented models, fields, or threshold bands.
    """
    contract_path = (
        Path(__file__).resolve().parent.parent / "COMPLIANCE_INTEGRATION_CONTRACT.md"
    )
    assert contract_path.exists(), "COMPLIANCE_INTEGRATION_CONTRACT.md must exist"

    content = contract_path.read_text(encoding="utf-8")

    # Verify key architectural invariants
    assert "FUTURE WORK" in content or "future work" in content
    assert "NO RUNTIME HTTP" in content or "NO RUNTIME" in content
    assert "is_deteriorating" in content
    assert "Circuit Breaking" in content or "circuit breaker" in content
    assert "Graceful Service Degradation" in content

    # Verify real compliance service endpoint and fields (Geethika's service)
    assert "/api/v1/compliance/screen" in content
    assert "ComplianceRequest" in content
    assert "ComplianceResponse" in content
    assert "entity_name" in content
    assert "entity_type" in content
    assert "country" in content
    assert "is_flagged" in content
    assert "MATCH_THRESHOLD" in content

    # Verify real Supplier Risk routes
    assert "/api/v1/supplier-risk/trend/{supplier_name}" in content
    assert "/api/v1/supplier-risk/trend" in content
    assert "GET /trend/{supplier_name}" not in content

    # Verify watchlists referenced
    assert "OFAC" in content and "UN" in content and "EU" in content

    # Verify invented models not in real main schema are absent
    assert "SanctionsResult" not in content, "Invented model 'SanctionsResult' must be removed from contract"

    # Verify real main compliance service fields are documented
    assert "transaction_value" in content, "Real main field 'transaction_value' must be in contract"
    assert "screening_tier" in content, "Real main field 'screening_tier' must be in contract"
    assert "enhanced_review_required" in content, "Real main field 'enhanced_review_required' must be in contract"
    assert "screening_action" in content, "Real main field 'screening_action' must be in contract"
    assert "case_id" in content, "Real main field 'case_id' must be in contract"
    assert "case_number" in content, "Real main field 'case_number' must be in contract"
    assert "case_status" in content, "Real main field 'case_status' must be in contract"

    # Verify tiered matching thresholds and absence of old single-threshold rule
    assert "LOW_TIER_MATCH_THRESHOLD" in content or "LOW → 90" in content
    assert "90" in content and "85" in content and "80" in content
    assert "MATCH_THRESHOLD = 90" not in content, "Old single-threshold MATCH_THRESHOLD=90 must not be active matching rule"

    # Verify stale 'NOT implemented' wording is absent
    assert "NOT implemented" not in content and "not implemented" not in content

    # Verify case management is documented
    assert "case management" in content.lower()

    # Verify §5 matrix gates on peak_risk_tier rather than current_risk_tier
    assert "peak_risk_tier" in content
    assert "| is_flagged / case_status | peak_risk_tier |" in content
    s5_section = content.split("## 5. Unified Risk Decision Matrix")[1].split("## 6.")[0]
    assert "current_risk_tier" not in s5_section, "§5 matrix must use peak_risk_tier, not current_risk_tier"

    # Verify uncapped per-headline score note
    assert "Per-headline score in `top_evidence` / `risk_trend[].evidence` is uncapped" in content

    # Verify decision matrix distinguishes flagged and cleared / unflagged states
    assert "case not `CLEARED`" in content or "CLEARED" in content
    assert "PROHIBITED / HARD BLOCK" in content
    assert "OPERATIONAL DISTRESS / HOLD" in content

    # Verify distinction of current vs proposed behavior
    assert "Current vs. Proposed/Future Behavior" in content or "Documented Current Behavior" in content


# Maintain alias for team lead review naming compatibility
test_compliance_contract_documentation_exists = test_compliance_contract_documentation_and_real_interface


def test_compliance_contract_json_examples_schema_validation():
    """
    Must Fix #4: Parse JSON blocks from COMPLIANCE_INTEGRATION_CONTRACT.md and validate
    them against the actual TrendAnalysisRequest and TrendResponse Pydantic models.
    Ensures documented contract examples cannot drift away from the API schema.
    """
    import re

    contract_path = (
        Path(__file__).resolve().parent.parent / "COMPLIANCE_INTEGRATION_CONTRACT.md"
    )
    content = contract_path.read_text(encoding="utf-8")

    # Extract all JSON code blocks
    json_blocks = re.findall(r"```json\s*(\{[\s\S]*?\})\s*```", content)
    assert len(json_blocks) >= 2, "Expected at least 2 JSON examples in the contract"

    parsed_blocks = []
    for block in json_blocks:
        try:
            parsed_blocks.append(json.loads(block))
        except json.JSONDecodeError as exc:
            pytest.fail(f"Invalid JSON block in contract: {exc}\nBlock:\n{block}")

    # Identify TrendAnalysisRequest example (contains 'supplier_name' and 'articles')
    trend_req_examples = [b for b in parsed_blocks if "supplier_name" in b and "articles" in b]
    assert len(trend_req_examples) >= 1, "Must contain a TrendAnalysisRequest example"
    trend_req = trend_req_examples[0]

    # Validate against Pydantic model
    validated_req = TrendAnalysisRequest(**trend_req)
    assert validated_req.supplier_name == "Apex Logistics"
    assert len(validated_req.articles) == 5
    assert validated_req.as_of_date == "2026-03-23"

    # Identify TrendResponse example (contains 'supplier', 'current_risk_score', 'risk_trend')
    trend_resp_examples = [b for b in parsed_blocks if "supplier" in b and "current_risk_score" in b and "risk_trend" in b]
    assert len(trend_resp_examples) >= 1, "Must contain a TrendResponse example"
    trend_resp = trend_resp_examples[0]

    # Validate against Pydantic model
    validated_resp = TrendResponse(**trend_resp)
    assert validated_resp.supplier == "Apex Logistics"
    assert validated_resp.current_risk_score == 100.0
    assert validated_resp.previous_risk_score == 27.93
    assert validated_resp.risk_delta == 72.07
    assert validated_resp.is_deteriorating is True
    assert validated_resp.trend_direction == "rising"

    # Verify self-consistency (no contradictory counts or null window starts when history exists)
    assert validated_resp.article_count == 5
    assert validated_resp.current_window_article_count == 3
    assert validated_resp.historical_article_count == 2
    assert validated_resp.article_count == validated_resp.current_window_article_count + validated_resp.historical_article_count
    assert validated_resp.window_end == "2026-03-23"
    assert validated_resp.window_start == "2026-02-21"
    assert validated_resp.previous_window_start is not None
    assert validated_resp.previous_window_end is not None



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


def test_trend_exact_deterioration_threshold_boundary():
    """
    Verify exact deterioration threshold (+-3.0) boundary behavior:
    - risk_delta == +3.0 => trend_direction='stable', is_deteriorating=False
    - risk_delta == -3.0 => trend_direction='stable', is_deteriorating=False
    - risk_delta == +3.01 within Low tier => trend_direction='rising', is_deteriorating=False (Low->Low)
    - risk_delta == -3.01 => trend_direction='falling', is_deteriorating=False
    """
    with patch("src.trend.predict") as mock_predict:
        def side_effect(supplier_name, headlines, config=None):
            hl = headlines[0] if headlines else ""
            if "target_plus_300" in hl:
                score = 53.0
            elif "target_minus_300" in hl:
                score = 47.0
            elif "target_plus_301" in hl:
                score = 53.01
            elif "target_minus_301" in hl:
                score = 46.99
            elif "hist_baseline" in hl:
                score = 50.0
            else:
                score = 0.0

            return {
                "supplier": supplier_name,
                "risk_score": score,
                "confidence": 0.85,
                "sentiment_breakdown": {"negative": 1, "positive": 0, "neutral": 0},
                "signals": [],
                "top_worst_3": [{"headline": hl, "score": score, "sentiment": "negative", "signals": []}],
            }

        mock_predict.side_effect = side_effect

        # 1. Exactly +3.0 delta -> stable, is_deteriorating=False
        records_plus_3 = [
            {"date": "2026-01-31", "headline": "hist_baseline"},
            {"date": "2026-03-31", "headline": "target_plus_300"},
        ]
        res_plus_3 = calculate_supplier_trend("BoundaryCorp", records_plus_3)
        assert res_plus_3["risk_delta"] == 3.0
        assert res_plus_3["trend_direction"] == "stable"
        assert res_plus_3["is_deteriorating"] is False
        assert "Risk is stable" in res_plus_3["deterioration_summary"]

        # 2. Exactly -3.0 delta -> stable, is_deteriorating=False
        records_minus_3 = [
            {"date": "2026-01-31", "headline": "hist_baseline"},
            {"date": "2026-03-31", "headline": "target_minus_300"},
        ]
        res_minus_3 = calculate_supplier_trend("BoundaryCorp", records_minus_3)
        assert res_minus_3["risk_delta"] == -3.0
        assert res_minus_3["trend_direction"] == "stable"
        assert res_minus_3["is_deteriorating"] is False
        assert "Risk is stable" in res_minus_3["deterioration_summary"]

        # 3. Exactly +3.01 delta within Low tier -> rising, is_deteriorating=False (Low->Low does not deteriorate)
        records_plus_301 = [
            {"date": "2026-01-31", "headline": "hist_baseline"},
            {"date": "2026-03-31", "headline": "target_plus_301"},
        ]
        res_plus_301 = calculate_supplier_trend("BoundaryCorp", records_plus_301)
        assert res_plus_301["risk_delta"] == 3.01
        assert res_plus_301["trend_direction"] == "rising"
        assert res_plus_301["is_deteriorating"] is False
        assert "not flagged as deteriorating" in res_plus_301["deterioration_summary"]

        # 4. Exactly -3.01 delta -> falling, is_deteriorating=False
        records_minus_301 = [
            {"date": "2026-01-31", "headline": "hist_baseline"},
            {"date": "2026-03-31", "headline": "target_minus_301"},
        ]
        res_minus_301 = calculate_supplier_trend("BoundaryCorp", records_minus_301)
        assert res_minus_301["risk_delta"] == -3.01
        assert res_minus_301["trend_direction"] == "falling"
        assert res_minus_301["is_deteriorating"] is False


def test_25_company_trend_dataset_full_cohort_sweep():
    """
    Verify full 25-company trend dataset cohort sweep:
    - Every supplier calculates without exception
    - current score is within [0, 100]
    - previous score is None or within [0, 100]
    - risk_delta is None or finite
    - trend_direction is one of rising/falling/stable as defined by implementation
    - is_deteriorating is boolean
    """
    import math

    trend_data = load_25_company_trend_dataset()
    assert len(trend_data) == 25, f"Expected 25 companies, got {len(trend_data)}"

    for supplier, records in trend_data.items():
        res = calculate_supplier_trend(supplier, records)
        assert res["supplier"] == supplier
        assert 0.0 <= res["current_risk_score"] <= 100.0
        if res["previous_risk_score"] is not None:
            assert 0.0 <= res["previous_risk_score"] <= 100.0
        if res["risk_delta"] is not None:
            assert isinstance(res["risk_delta"], (int, float))
            assert not math.isnan(res["risk_delta"])
            assert not math.isinf(res["risk_delta"])
        assert res["trend_direction"] in {"rising", "falling", "stable"}
        assert isinstance(res["is_deteriorating"], bool)
        assert res["article_count"] == len(records)


def test_trend_direction_across_operational_risk_tiers():
    """
    Verify representative tier and trend direction combinations:
    - Rising + Medium
    - Rising + High
    - Falling + High
    - Falling + Critical
    """
    # 1. Rising + Medium: Clean past, strike in current window
    records_rising_medium = [
        {"date": "2026-01-15", "headline": "Alpha Corp reports positive earnings and strong profit."},
        {"date": "2026-03-20", "headline": "Alpha Corp workers go on strike over contract disputes."},
    ]
    res_rm = calculate_supplier_trend("Alpha Corp", records_rising_medium)
    assert res_rm["trend_direction"] == "rising"
    assert res_rm["is_deteriorating"] is True
    assert assign_risk_tier(res_rm["current_risk_score"]) == "Medium"

    # 2. Rising + High: Clean past, strike and disruption in current window
    records_rising_high = [
        {"date": "2026-01-15", "headline": "Beta Corp reports positive earnings and strong profit."},
        {"date": "2026-03-20", "headline": "Beta Corp workers go on strike amidst severe supply disruption."},
    ]
    res_rh = calculate_supplier_trend("Beta Corp", records_rising_high)
    assert res_rh["trend_direction"] == "rising"
    assert res_rh["is_deteriorating"] is True
    assert assign_risk_tier(res_rh["current_risk_score"]) == "High"

    # 3. Falling + High: Catastrophic past (bankruptcy + default), high in current window
    records_falling_high = [
        {"date": "2026-01-15", "headline": "Gamma Corp files for bankruptcy following debt default."},
        {"date": "2026-03-20", "headline": "Gamma Corp workers go on strike amidst severe supply disruption."},
    ]
    res_fh = calculate_supplier_trend("Gamma Corp", records_falling_high)
    assert res_fh["trend_direction"] == "falling"
    assert res_fh["is_deteriorating"] is False
    assert assign_risk_tier(res_fh["current_risk_score"]) == "High"

    # 4. Falling + Critical: Multi-catastrophic past, single acute event in current window
    records_falling_critical = [
        {"date": "2026-01-15", "headline": "Delta Corp hit with bankruptcy, fraud investigation, and debt default."},
        {"date": "2026-03-20", "headline": "Delta Corp files for bankruptcy."},
    ]
    res_fc = calculate_supplier_trend("Delta Corp", records_falling_critical)
    assert res_fc["trend_direction"] == "falling"
    assert res_fc["is_deteriorating"] is False
    assert assign_risk_tier(res_fc["current_risk_score"]) == "Critical"
