"""
Unit and integration tests for Milestone 2: Confidence and Evidence.

Validates:
- Evidence presence, ranking, and explanation per trend point
- Timeline-level top evidence across dates
- Clean/zero-risk evidence handling
- Confidence bounds and volume/agreement/recency behavior
- Duplicate headline deduplication
- Failure paths (empty, unknown supplier, malformed)
- Backward compatibility of all existing /predict endpoints
"""

from unittest.mock import patch
from fastapi.testclient import TestClient
import pytest

from src.analyze import app
from src.config import Settings
from src.trend import (
    calculate_recency_weighted_confidence,
    calculate_supplier_trend,
)


@pytest.fixture(autouse=True)
def mock_sentiment():
    """Mock analyze_sentiment to avoid downloading FinBERT during unit tests."""
    with patch("src.predict.analyze_sentiment") as mock:
        def side_effect(text):
            lower_text = text.lower()
            if any(w in lower_text for w in [
                "bankruptcy", "fraud", "strike", "lawsuit", "sanction",
                "disruption", "recall", "layoff", "shortage", "default", "downgrade"
            ]):
                return {"label": "negative", "confidence": 0.99}
            if "positive" in lower_text or "record" in lower_text or "profit" in lower_text:
                return {"label": "positive", "confidence": 0.95}
            return {"label": "neutral", "confidence": 0.99}
        mock.side_effect = side_effect
        yield mock


# ------------------------------------------------------------------
# 1. Evidence Presence and Structure
# ------------------------------------------------------------------

def test_trend_point_contains_evidence_structure():
    """Every trend point must contain an evidence list with required fields."""
    records = [
        {
            "date": "2026-01-05",
            "headline": "Tesla announces a major recall of 2 million vehicles over autopilot software issues.",
        }
    ]
    result = calculate_supplier_trend("Tesla", records)
    point = result["risk_trend"][0]

    assert "evidence" in point
    assert isinstance(point["evidence"], list)
    assert len(point["evidence"]) == 1

    ev = point["evidence"][0]
    assert ev["headline"] == records[0]["headline"]
    assert ev["sentiment"] == "negative"
    assert ev["score"] > 0
    assert "signals" in ev
    assert len(ev["signals"]) > 0

    signal = ev["signals"][0]
    assert signal["keyword"] == "recall"
    assert signal["weight"] == 30


def test_evidence_ranking_highest_risk_first():
    """Evidence for a date with multiple headlines must be deterministically ranked with highest risk first."""
    records = [
        {
            "date": "2026-01-10",
            "headline": "Supplier reports positive earnings for Q3.",  # zero risk
        },
        {
            "date": "2026-01-10",
            "headline": "Supplier files for emergency bankruptcy after fraud scandal.",  # critical risk
        },
        {
            "date": "2026-01-10",
            "headline": "Supplier faces minor shipment delays.",  # minor risk
        },
    ]
    result = calculate_supplier_trend("SupplierX", records)
    evidence = result["risk_trend"][0]["evidence"]

    assert len(evidence) == 3
    # Check descending score ordering
    assert evidence[0]["score"] >= evidence[1]["score"] >= evidence[2]["score"]
    # The bankruptcy/fraud headline must be ranked first
    assert "bankruptcy" in evidence[0]["headline"]


def test_clean_date_evidence_handling():
    """On clean/positive dates, evidence contains zero-risk headlines with score 0 and empty signals."""
    records = [
        {
            "date": "2026-02-01",
            "headline": "Company reports record positive earnings and profit growth.",
        }
    ]
    result = calculate_supplier_trend("CleanCorp", records)
    point = result["risk_trend"][0]

    assert point["risk_score"] == 0.0
    assert len(point["evidence"]) == 1
    ev = point["evidence"][0]
    assert ev["score"] == 0.0
    assert ev["signals"] == []
    assert ev["sentiment"] == "positive"


def test_timeline_top_evidence_across_dates():
    """Top evidence on timeline level aggregates the worst headlines across all dates."""
    records = [
        {"date": "2026-01-01", "headline": "Company reports positive revenue."},
        {"date": "2026-01-15", "headline": "Company faces strike and workers walkout."},  # moderate
        {"date": "2026-02-01", "headline": "Company files for bankruptcy amid debt default."},  # extreme
        {"date": "2026-02-15", "headline": "Company hit with major lawsuit."},  # moderate
    ]
    result = calculate_supplier_trend("MultiDateCorp", records)

    assert "top_evidence" in result
    top_ev = result["top_evidence"]
    assert len(top_ev) <= 3
    # Worst headline across entire timeline (bankruptcy) must be first
    assert "bankruptcy" in top_ev[0]["headline"]
    assert top_ev[0]["score"] >= top_ev[1]["score"]


# ------------------------------------------------------------------
# 2. Confidence Calculation Tests
# ------------------------------------------------------------------

def test_confidence_bounds_date_and_timeline():
    """All date-level confidences and timeline overall confidence must be bounded in [0.0, 1.0]."""
    records = [
        {"date": f"2026-01-{i:02d}", "headline": "Company faces supplier disruption."}
        for i in range(1, 20)
    ]
    result = calculate_supplier_trend("BoundSupplier", records)

    assert 0.0 <= result["overall_confidence"] <= 1.0
    for point in result["risk_trend"]:
        assert 0.0 <= point["confidence"] <= 1.0


def test_zero_headlines_yields_zero_confidence():
    """Empty records yields 0.0 overall confidence and empty top evidence."""
    result = calculate_supplier_trend("EmptySupplier", [])

    assert result["overall_confidence"] == 0.0
    assert result["top_evidence"] == []
    assert result["risk_trend"] == []


def test_recency_weighted_confidence_behavior():
    """
    Timeline with fresh recent risk has higher recency-weighted confidence
    than an identical risk event from 180 days in the past.
    """
    # Case A: High risk today (2026-06-30), mild clean news earlier
    trend_recent_risk = [
        {"date": "2026-01-01", "confidence": 0.2, "headline_count": 1},
        {"date": "2026-06-30", "confidence": 0.8, "headline_count": 1},
    ]

    # Case B: High risk 180 days ago (2026-01-01), mild clean news today (2026-06-30)
    trend_old_risk = [
        {"date": "2026-01-01", "confidence": 0.8, "headline_count": 1},
        {"date": "2026-06-30", "confidence": 0.2, "headline_count": 1},
    ]

    conf_recent = calculate_recency_weighted_confidence(trend_recent_risk, half_life_days=30.0)
    conf_old = calculate_recency_weighted_confidence(trend_old_risk, half_life_days=30.0)

    # When the strong evidence is recent, the overall recency-weighted confidence is higher
    assert conf_recent > conf_old
    assert (conf_recent - conf_old) > 0.4


def test_configurable_recency_half_life():
    """Settings.recency_half_life_days customizes decay rate."""
    trend_points = [
        {"date": "2026-01-01", "confidence": 0.8, "headline_count": 1},
        {"date": "2026-03-01", "confidence": 0.2, "headline_count": 1},
    ]
    # Fast decay (half-life = 7 days): older observation decays rapidly
    conf_fast_decay = calculate_recency_weighted_confidence(trend_points, half_life_days=7.0)

    # Slow decay (half-life = 365 days): older observation retains high weight
    conf_slow_decay = calculate_recency_weighted_confidence(trend_points, half_life_days=365.0)

    assert conf_fast_decay < conf_slow_decay


# ------------------------------------------------------------------
# 3. Duplicate Headlines & Anti-Inflation Tests
# ------------------------------------------------------------------

def test_duplicate_headlines_do_not_duplicate_evidence_or_inflate():
    """Duplicate headlines on same date do not duplicate evidence items or inflate confidence."""
    headline = "Supplier faces major recall over defective parts."
    records_single = [{"date": "2026-01-10", "headline": headline}]
    records_duplicated = [
        {"date": "2026-01-10", "headline": headline},
        {"date": "2026-01-10", "headline": headline},
        {"date": "2026-01-10", "headline": f"  {headline}  "},
    ]

    res_single = calculate_supplier_trend("DupSupplier", records_single)
    res_dup = calculate_supplier_trend("DupSupplier", records_duplicated)

    # Evidence list must only have 1 item
    assert len(res_dup["risk_trend"][0]["evidence"]) == 1
    # Scores and confidences must be identical
    assert res_dup["risk_trend"][0]["risk_score"] == res_single["risk_trend"][0]["risk_score"]
    assert res_dup["risk_trend"][0]["confidence"] == res_single["risk_trend"][0]["confidence"]
    assert res_dup["overall_confidence"] == res_single["overall_confidence"]


# ------------------------------------------------------------------
# 4. Failure Paths & Validation
# ------------------------------------------------------------------

def test_failure_path_unknown_supplier_trend_endpoint():
    """GET trend for unknown supplier returns 200 with empty risk_trend, top_evidence, and 0.0 confidence."""
    with TestClient(app) as client:
        response = client.get("/api/v1/supplier-risk/trend/NonExistentSupplierXYZ")
        assert response.status_code == 200
        data = response.json()

        assert data["supplier"] == "NonExistentSupplierXYZ"
        assert data["risk_trend"] == []
        assert data["top_evidence"] == []
        assert data["overall_confidence"] == 0.0


def test_failure_path_malformed_records():
    """Records missing headline or date field raise ValueError."""
    with pytest.raises(ValueError, match="missing required 'headline' field"):
        calculate_supplier_trend("BadSupplier", [{"date": "2026-01-01"}])

    with pytest.raises(ValueError, match="missing required 'date' field"):
        calculate_supplier_trend("BadSupplier", [{"headline": "Some headline."}])


# ------------------------------------------------------------------
# 5. API Integration Tests (Evidence & Confidence in Trend Endpoints)
# ------------------------------------------------------------------

def test_api_get_trend_includes_evidence_and_overall_confidence():
    """GET /api/v1/supplier-risk/trend/{supplier_name} returns evidence and overall_confidence."""
    with TestClient(app) as client:
        response = client.get("/api/v1/supplier-risk/trend/Tesla")
        assert response.status_code == 200
        data = response.json()

        assert data["supplier"] == "Tesla"
        assert "overall_confidence" in data
        assert isinstance(data["overall_confidence"], float)
        assert 0.0 <= data["overall_confidence"] <= 1.0

        assert "top_evidence" in data
        assert isinstance(data["top_evidence"], list)
        assert len(data["top_evidence"]) > 0

        # Check evidence in each trend point
        point = data["risk_trend"][0]
        assert "evidence" in point
        assert isinstance(point["evidence"], list)
        assert len(point["evidence"]) > 0
        ev = point["evidence"][0]
        assert "headline" in ev
        assert "sentiment" in ev
        assert "score" in ev
        assert "signals" in ev


def test_api_post_trend_includes_evidence_and_overall_confidence():
    """POST /api/v1/supplier-risk/trend returns evidence in response."""
    with TestClient(app) as client:
        payload = {
            "supplier_name": "DynamicSupplier",
            "articles": [
                {
                    "date": "2026-02-15",
                    "headline": "DynamicSupplier workers declare strike over wage disputes.",
                },
                {
                    "date": "2026-01-10",
                    "headline": "DynamicSupplier reports positive earnings.",
                },
            ],
        }
        response = client.post("/api/v1/supplier-risk/trend", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["supplier"] == "DynamicSupplier"
        assert "overall_confidence" in data
        assert "top_evidence" in data
        assert len(data["top_evidence"]) > 0

        # Check evidence in trend points
        p_strike = [p for p in data["risk_trend"] if p["date"] == "2026-02-15"][0]
        assert len(p_strike["evidence"]) == 1
        assert "strike" in p_strike["evidence"][0]["signals"][0]["keyword"]


# ------------------------------------------------------------------
# 6. Backward Compatibility: /predict Response Contracts Intact
# ------------------------------------------------------------------

def test_predict_endpoint_response_contracts_strictly_intact():
    """
    Verify POST /predict, /api/v1/supplier-risk/predict, and /api/v1/supplier-risk/analyze
    strictly retain the original response contract without any modifications.
    """
    with TestClient(app) as client:
        payload = {
            "supplier_name": "TestCorp",
            "headlines": [
                "TestCorp announces major recall of defective products.",
                "TestCorp reports positive earnings.",
            ],
        }

        endpoints = [
            "/predict",
            "/api/v1/supplier-risk/predict",
            "/api/v1/supplier-risk/analyze",
        ]

        expected_summary_keys = {
            "supplier",
            "risk_score",
            "confidence",
            "sentiment_breakdown",
            "signals",
            "top_worst_3",
        }
        expected_sentiment_keys = {"positive", "neutral", "negative"}

        for ep in endpoints:
            response = client.post(ep, json=payload)
            assert response.status_code == 200
            data = response.json()

            assert "supplier_summary" in data
            assert "TestCorp" in data["supplier_summary"]

            summary = data["supplier_summary"]["TestCorp"]
            assert set(summary.keys()) == expected_summary_keys
            assert set(summary["sentiment_breakdown"].keys()) == expected_sentiment_keys
            assert isinstance(summary["risk_score"], float)
            assert isinstance(summary["confidence"], float)
            assert isinstance(summary["top_worst_3"], list)
