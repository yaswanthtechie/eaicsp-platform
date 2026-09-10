"""
Unit and integration tests for the date-aware Supplier Risk Trend pipeline.
"""

from unittest.mock import patch
from fastapi.testclient import TestClient
import pytest

from src.analyze import app
from src.data import load_trend_headlines
from src.trend import calculate_supplier_trend, validate_date


@pytest.fixture(autouse=True)
def mock_sentiment():
    """Mock analyze_sentiment to avoid downloading FinBERT during unit tests."""
    with patch("src.predict.analyze_sentiment") as mock:
        def side_effect(text):
            lower_text = text.lower()
            if any(w in lower_text for w in ["bankruptcy", "fraud", "strike", "lawsuit", "sanction", "disruption", "recall", "layoff"]):
                return {"label": "negative", "confidence": 0.99}
            if "positive" in lower_text or "record" in lower_text or "profit" in lower_text:
                return {"label": "positive", "confidence": 0.95}
            return {"label": "neutral", "confidence": 0.99}
        mock.side_effect = side_effect
        yield mock


# ------------------------------------------------------------------
# 1. Date Validation Tests
# ------------------------------------------------------------------

def test_validate_date_valid():
    """Verify valid ISO dates pass validation."""
    assert validate_date("2026-01-01") == "2026-01-01"
    assert validate_date("2026-12-31") == "2026-12-31"
    assert validate_date("2024-02-29") == "2024-02-29"  # leap year


def test_validate_date_invalid_month():
    """Verify '2026-99-99' fails validation."""
    with pytest.raises(ValueError, match="Invalid calendar date"):
        validate_date("2026-99-99")


def test_validate_date_invalid_day():
    """Verify '2026-02-30' fails validation."""
    with pytest.raises(ValueError, match="Invalid calendar date"):
        validate_date("2026-02-30")


def test_validate_date_not_a_date_string():
    """Verify 'not-a-date' fails validation."""
    with pytest.raises(ValueError, match="Expected ISO format YYYY-MM-DD"):
        validate_date("not-a-date")


def test_validate_date_slashed_format():
    """Verify '2026/01/01' fails validation."""
    with pytest.raises(ValueError, match="Expected ISO format YYYY-MM-DD"):
        validate_date("2026/01/01")


def test_validate_date_non_string():
    """Verify non-string types fail validation."""
    with pytest.raises(ValueError, match="Date must be a string"):
        validate_date(12345)


# ------------------------------------------------------------------
# 2. Trend Engine Functionality & Edge Cases
# ------------------------------------------------------------------

def test_trend_empty_records():
    """Empty records list returns empty risk_trend."""
    result = calculate_supplier_trend("Tesla", [])
    assert result["supplier"] == "Tesla"
    assert result["risk_trend"] == []


def test_trend_blank_supplier_name():
    """Blank supplier name raises ValueError."""
    with pytest.raises(ValueError, match="supplier_name cannot be blank"):
        calculate_supplier_trend("   ", [])


def test_trend_dates_out_of_order_sorted_chronologically():
    """Dates received out of order must be returned in chronological order."""
    records = [
        {"date": "2026-03-15", "headline": "Tesla expands Gigafactory operations in Texas."},
        {"date": "2026-01-05", "headline": "Tesla announces a major recall of 2 million vehicles."},
        {"date": "2026-02-10", "headline": "Tesla reports record positive earnings."},
    ]

    result = calculate_supplier_trend("Tesla", records)
    trend = result["risk_trend"]

    assert len(trend) == 3
    assert trend[0]["date"] == "2026-01-05"
    assert trend[1]["date"] == "2026-02-10"
    assert trend[2]["date"] == "2026-03-15"


def test_trend_multiple_headlines_same_date():
    """Multiple headlines on the same date are aggregated into one trend point."""
    records = [
        {"date": "2026-01-15", "headline": "Boeing faces new lawsuit over safety violations."},
        {"date": "2026-01-15", "headline": "Boeing machinists go on strike demanding better wages."},
    ]

    result = calculate_supplier_trend("Boeing", records)
    trend = result["risk_trend"]

    assert len(trend) == 1
    assert trend[0]["date"] == "2026-01-15"
    assert trend[0]["headline_count"] == 2
    assert trend[0]["risk_score"] > 0


def test_trend_duplicate_headlines_deduplicated():
    """Duplicate headlines on same date do not artificially inflate score or headline count."""
    headline = "Intel faces unexpected raw-material shortage delaying new fab construction."
    records_single = [
        {"date": "2026-01-20", "headline": headline},
    ]
    records_duplicate = [
        {"date": "2026-01-20", "headline": headline},
        {"date": "2026-01-20", "headline": headline},
        {"date": "2026-01-20", "headline": f"  {headline}  "},
    ]

    res_single = calculate_supplier_trend("Intel", records_single)
    res_dup = calculate_supplier_trend("Intel", records_duplicate)

    # Headline count must reflect unique evidence
    assert res_dup["risk_trend"][0]["headline_count"] == 1
    assert res_dup["risk_trend"][0]["risk_score"] == res_single["risk_trend"][0]["risk_score"]
    assert res_dup["risk_trend"][0]["confidence"] == res_single["risk_trend"][0]["confidence"]


def test_trend_high_risk_followed_by_neutral():
    """High risk headline followed by neutral headlines reflects changing risk trajectory."""
    records = [
        {"date": "2026-01-01", "headline": "TechCorp files for bankruptcy after massive fraud scandal."},
        {"date": "2026-01-15", "headline": "TechCorp reports routine administrative board meeting."},
        {"date": "2026-02-01", "headline": "TechCorp announces opening of new distribution facility."},
    ]

    result = calculate_supplier_trend("TechCorp", records)
    trend = result["risk_trend"]

    assert len(trend) == 3
    # Day 1 should be severe risk (bankruptcy + fraud)
    assert trend[0]["risk_score"] >= 50.0
    # Later days should be low risk
    assert trend[1]["risk_score"] <= 25.0
    assert trend[2]["risk_score"] <= 25.0
    # Trend demonstrates risk reduction over time
    assert trend[0]["risk_score"] > trend[1]["risk_score"]


def test_trend_missing_date_field():
    """Record without date field raises ValueError."""
    records = [{"headline": "Some headline."}]
    with pytest.raises(ValueError, match="missing required 'date' field"):
        calculate_supplier_trend("SupplierX", records)


def test_trend_missing_headline_field():
    """Record without headline field raises ValueError."""
    records = [{"date": "2026-01-01"}]
    with pytest.raises(ValueError, match="missing required 'headline' field"):
        calculate_supplier_trend("SupplierX", records)


# ------------------------------------------------------------------
# 3. Data Loading Integration Tests
# ------------------------------------------------------------------

def test_load_trend_headlines_from_dataset():
    """Verify supplier_trend_headlines.json loads 10 suppliers with valid date-aware records."""
    trend_data = load_trend_headlines()

    assert len(trend_data) == 10
    expected_suppliers = {
        "Boeing", "Intel", "Tesla", "Nissan", "Foxconn",
        "TSMC", "Maersk", "BASF", "Siemens", "Apex Logistics",
    }
    assert set(trend_data.keys()) == expected_suppliers

    for supplier, articles in trend_data.items():
        assert len(articles) == 12
        for article in articles:
            assert "date" in article
            assert "headline" in article
            validate_date(article["date"])


# ------------------------------------------------------------------
# 4. API Endpoint Tests
# ------------------------------------------------------------------

def test_api_get_trend_valid_supplier():
    """GET /api/v1/supplier-risk/trend/{supplier_name} returns 200 with chronological points."""
    with TestClient(app) as client:
        response = client.get("/api/v1/supplier-risk/trend/Tesla")
        assert response.status_code == 200
        data = response.json()

        assert data["supplier"] == "Tesla"
        assert "risk_trend" in data
        trend = data["risk_trend"]
        assert len(trend) > 0

        # Verify trend point schema
        point = trend[0]
        assert "date" in point
        assert "risk_score" in point
        assert "confidence" in point
        assert "headline_count" in point

        # Verify strictly chronological
        dates = [p["date"] for p in trend]
        assert dates == sorted(dates)


def test_api_get_trend_unknown_supplier():
    """GET trend for unknown supplier returns 200 with empty risk_trend."""
    with TestClient(app) as client:
        response = client.get("/api/v1/supplier-risk/trend/NonExistentSupplier123")
        assert response.status_code == 200
        data = response.json()

        assert data["supplier"] == "NonExistentSupplier123"
        assert data["risk_trend"] == []


def test_api_get_trend_blank_supplier():
    """GET trend with whitespace-only supplier returns 400."""
    with TestClient(app) as client:
        response = client.get("/api/v1/supplier-risk/trend/%20")
        assert response.status_code == 400


def test_api_post_trend_valid():
    """POST /api/v1/supplier-risk/trend returns 200 with calculated trend."""
    with TestClient(app) as client:
        payload = {
            "supplier_name": "DynamicSupplier",
            "articles": [
                {"date": "2026-02-15", "headline": "DynamicSupplier faces supply disruption."},
                {"date": "2026-01-10", "headline": "DynamicSupplier reports positive earnings."},
            ],
        }
        response = client.post("/api/v1/supplier-risk/trend", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["supplier"] == "DynamicSupplier"
        assert len(data["risk_trend"]) == 2
        # Chronological ordering check
        assert data["risk_trend"][0]["date"] == "2026-01-10"
        assert data["risk_trend"][1]["date"] == "2026-02-15"


def test_api_post_trend_invalid_date():
    """POST /api/v1/supplier-risk/trend with invalid date returns 422 validation error."""
    with TestClient(app) as client:
        payload = {
            "supplier_name": "TestSupplier",
            "articles": [
                {"date": "2026-99-99", "headline": "Some headline."},
            ],
        }
        response = client.post("/api/v1/supplier-risk/trend", json=payload)
        assert response.status_code == 422


# ------------------------------------------------------------------
# 5. Backward Compatibility Verification
# ------------------------------------------------------------------

def test_predict_endpoint_response_contract_unchanged():
    """Verify POST /predict returns exactly the original schema fields."""
    with TestClient(app) as client:
        payload = {
            "supplier_name": "CompatSupplier",
            "headlines": [
                "CompatSupplier announces recall due to defect.",
                "CompatSupplier reports positive earnings.",
            ],
        }
        response = client.post("/predict", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert "supplier_summary" in data
        assert "CompatSupplier" in data["supplier_summary"]

        summary = data["supplier_summary"]["CompatSupplier"]
        expected_keys = {
            "supplier",
            "risk_score",
            "confidence",
            "sentiment_breakdown",
            "signals",
            "top_worst_3",
        }
        assert set(summary.keys()) == expected_keys
        assert set(summary["sentiment_breakdown"].keys()) == {"positive", "neutral", "negative"}
