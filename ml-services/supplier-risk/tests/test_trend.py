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
            if any(w in lower_text for w in [
                "bankruptcy", "fraud", "strike", "lawsuit", "sanction",
                "disruption", "recall", "layoff", "default", "insolvency",
                "downgrade", "restructuring"
            ]):
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


def test_api_get_trend_supplier_lookup_is_case_insensitive():
    """GET trend normalizes supplier name casing before dataset lookup."""
    with TestClient(app) as client:
        response = client.get("/api/v1/supplier-risk/trend/tesla")

        assert response.status_code == 200
        assert response.json()["supplier"] == "Tesla"
        assert response.json()["risk_trend"]


def test_api_get_trend_unknown_supplier():
    """GET trend for an unknown supplier returns 404."""
    with TestClient(app) as client:
        response = client.get("/api/v1/supplier-risk/trend/NonExistentSupplier123")
        assert response.status_code == 404


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


def test_api_get_trend_extended_benchmark_suppliers():
    """Verify GET trend returns valid points and evidence for all 5 extended benchmark suppliers."""
    extended_suppliers = [
        "Northvolt",
        "ASML",
        "Glencore",
        "Lockheed Martin",
        "Evergreen Marine",
    ]
    with TestClient(app) as client:
        for supplier in extended_suppliers:
            response = client.get(f"/api/v1/supplier-risk/trend/{supplier}")
            assert response.status_code == 200, f"Failed for {supplier}: {response.text}"
            data = response.json()

            assert data["supplier"] == supplier
            assert "risk_trend" in data
            assert len(data["risk_trend"]) > 0, f"Expected trend points for {supplier}"
            assert data["overall_confidence"] > 0.0, f"Expected non-zero confidence for {supplier}"
            assert len(data["top_evidence"]) > 0, f"Expected top evidence for {supplier}"

            # Verify points are strictly chronological
            dates = [p["date"] for p in data["risk_trend"]]
            assert dates == sorted(dates), f"Dates out of order for {supplier}"


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


# ------------------------------------------------------------------
# 6. Entity-Level Time-Aware Risk Aggregation (MUST-FIX #4)
# ------------------------------------------------------------------

def test_trend_multi_article_aggregation():
    """Verify multiple dated articles for one supplier are aggregated into a single score."""
    records = [
        {"date": "2026-03-01", "headline": "Acme Corp files for bankruptcy amid massive debt default."},
        {"date": "2026-03-15", "headline": "Acme Corp reports routine facility inspection."},
        {"date": "2026-03-20", "headline": "Acme Corp expands manufacturing partnership in Europe."},
    ]
    res = calculate_supplier_trend("Acme Corp", records)
    assert res["supplier"] == "Acme Corp"
    assert res["article_count"] == 3
    assert res["current_window_article_count"] == 3
    assert res["window_days"] == 30
    assert res["window_start"] is not None
    assert res["window_end"] == "2026-03-20"

    # Score must be a weighted aggregate, not just the single latest article
    single_latest = calculate_supplier_trend("Acme Corp", [records[-1]])["current_risk_score"]
    single_earliest = calculate_supplier_trend("Acme Corp", [records[0]])["current_risk_score"]
    assert res["current_risk_score"] != single_latest
    assert min(single_latest, single_earliest) <= res["current_risk_score"] <= max(single_latest, single_earliest)


def test_trend_recency_decay_weighting():
    """Verify that inside a rolling window, predict() aggregates without artificial recency decay."""
    # Two identical-severity events placed at different times relative to anchor date (2026-03-30)
    # Event A: High risk today (2026-03-30), Low risk 28 days ago (2026-03-02)
    records_recent_bad = [
        {"date": "2026-03-02", "headline": "Beta Corp reports positive earnings and strong demand."},
        {"date": "2026-03-30", "headline": "Beta Corp hit with severe sanction and product recall."},
    ]
    # Event B: High risk 28 days ago (2026-03-02), Low risk today (2026-03-30)
    records_old_bad = [
        {"date": "2026-03-02", "headline": "Beta Corp hit with severe sanction and product recall."},
        {"date": "2026-03-30", "headline": "Beta Corp reports positive earnings and strong demand."},
    ]

    res_recent_bad = calculate_supplier_trend("Beta Corp", records_recent_bad)
    res_old_bad = calculate_supplier_trend("Beta Corp", records_old_bad)

    # Inside a window, scores are not decayed; the window itself is the recency boundary
    assert res_recent_bad["current_risk_score"] == res_old_bad["current_risk_score"]


def test_trend_window_exclusion():
    """Verify older articles outside the 30-day window do not contribute to current_risk_score."""
    # Anchor date: 2026-03-31
    # Article 1: 2026-01-15 (75 days ago, well outside 30-day window) -> Severe risk (bankruptcy)
    # Article 2: 2026-03-31 (today) -> Zero risk (positive earnings)
    records = [
        {"date": "2026-01-15", "headline": "Gamma Inc declares bankruptcy and liquidation."},
        {"date": "2026-03-31", "headline": "Gamma Inc reports record positive profits and new contracts."},
    ]
    res = calculate_supplier_trend("Gamma Inc", records)
    assert res["article_count"] == 2
    assert res["current_window_article_count"] == 1
    assert res["historical_article_count"] == 1
    # Current score must only reflect the article inside the 30-day window
    res_only_current = calculate_supplier_trend("Gamma Inc", [records[1]])
    assert res["current_risk_score"] == res_only_current["current_risk_score"]
    # Previous score must capture the historical article
    assert res["previous_risk_score"] is not None
    assert res["previous_risk_score"] > 50.0


def test_trend_changing_recency_half_life_deterministic():
    """Verify changing recency_half_life_days alters weights and aggregate score deterministically."""
    from src.config import Settings
    records = [
        {"date": "2026-03-01", "headline": "Delta Corp announces major recall due to defect."},
        {"date": "2026-03-31", "headline": "Delta Corp reports routine positive earnings."},
    ]
    # Current window score uses predict() without internal decay
    cfg_short = Settings(recency_half_life_days=5.0)
    res_short = calculate_supplier_trend("Delta Corp", records, config=cfg_short)

    cfg_long = Settings(recency_half_life_days=60.0)
    res_long = calculate_supplier_trend("Delta Corp", records, config=cfg_long)

    assert res_short["current_risk_score"] == res_long["current_risk_score"]
    # Overall timeline confidence is recency-weighted by half-life
    assert res_short["overall_confidence"] != res_long["overall_confidence"]


def test_trend_rising_direction_detected():
    """Verify a supplier with deteriorating risk over time is classified as 'rising'."""
    records = [
        # Previous window: clean/positive news
        {"date": "2026-01-20", "headline": "Epsilon Corp reports positive earnings and revenue growth."},
        {"date": "2026-02-10", "headline": "Epsilon Corp signs positive supply agreement with major partner."},
        # Current window: multiple severe risk events
        {"date": "2026-03-05", "headline": "Epsilon Corp workers go on strike shutting down production."},
        {"date": "2026-03-20", "headline": "Epsilon Corp hit with lawsuit over fraud and supply disruption."},
    ]
    res = calculate_supplier_trend("Epsilon Corp", records)
    assert res["previous_risk_score"] is not None
    assert res["current_risk_score"] > res["previous_risk_score"]
    assert res["trend_direction"] == "rising"


def test_trend_falling_direction_detected():
    """Verify a supplier recovering from past distress is classified as 'falling'."""
    records = [
        # Previous window: severe risk events
        {"date": "2026-01-20", "headline": "Zeta Corp faces bankruptcy and severe debt default."},
        {"date": "2026-02-10", "headline": "Zeta Corp hit with regulator investigation and sanction."},
        # Current window: recovery and clean operations
        {"date": "2026-03-05", "headline": "Zeta Corp completes restructuring and resolves dispute."},
        {"date": "2026-03-20", "headline": "Zeta Corp reports record positive profits and new expansion."},
    ]
    res = calculate_supplier_trend("Zeta Corp", records)
    assert res["previous_risk_score"] is not None
    assert res["current_risk_score"] < res["previous_risk_score"]
    assert res["trend_direction"] == "falling"


def test_trend_stable_direction_detected():
    """Verify a supplier with steady risk levels is classified as 'stable'."""
    records = [
        # Previous window: neutral news
        {"date": "2026-01-20", "headline": "Eta Corp holds routine annual shareholder meeting."},
        {"date": "2026-02-10", "headline": "Eta Corp releases quarterly operational update."},
        # Current window: consistent neutral news
        {"date": "2026-03-05", "headline": "Eta Corp continues standard logistics operations."},
        {"date": "2026-03-20", "headline": "Eta Corp maintains existing supply contracts."},
    ]
    res = calculate_supplier_trend("Eta Corp", records)
    assert res["previous_risk_score"] is not None
    assert abs(res["current_risk_score"] - res["previous_risk_score"]) <= 3.0
    assert res["trend_direction"] == "stable"


def test_trend_supplier_isolation():
    """Verify records for other suppliers do not contaminate the target supplier's trend."""
    records = [
        {"supplier": "TargetSupplier", "date": "2026-03-10", "headline": "TargetSupplier reports positive earnings."},
        {"supplier": "OtherSupplier", "date": "2026-03-10", "headline": "OtherSupplier declares bankruptcy after massive fraud scandal."},
    ]
    res = calculate_supplier_trend("TargetSupplier", records)
    assert res["supplier"] == "TargetSupplier"
    assert res["article_count"] == 1
    # The bankruptcy headline from OtherSupplier must NOT affect TargetSupplier
    assert res["current_risk_score"] == 0.0


def test_trend_invalid_configuration():
    """Verify invalid trend configuration parameters raise ValueError."""
    from src.config import Settings
    with pytest.raises(ValueError, match="Trend window days must be greater than zero"):
        Settings(trend_window_days=0)

    with pytest.raises(ValueError, match="Trend window days must be an integer"):
        Settings(trend_window_days="invalid")

    with pytest.raises(ValueError, match="Trend direction threshold cannot be negative"):
        Settings(trend_direction_threshold=-1.0)


def test_aggregate_supplier_trends_multi_supplier():
    """Verify aggregate_supplier_trends groups multiple suppliers and calculates trends for each."""
    from src.trend import aggregate_supplier_trends
    records = [
        {"supplier": "SupplierA", "date": "2026-03-10", "headline": "SupplierA reports positive earnings."},
        {"supplier": "SupplierB", "date": "2026-03-10", "headline": "SupplierB hit with strike and supply disruption."},
    ]
    results = aggregate_supplier_trends(records)
    assert "SupplierA" in results
    assert "SupplierB" in results
    assert results["SupplierA"]["current_risk_score"] < results["SupplierB"]["current_risk_score"]
    assert results["SupplierA"]["trend_direction"] == "stable"


# ------------------------------------------------------------------
# 7. Regression & Validation Tests (Must Fix #1 & Must Fix #2)
# ------------------------------------------------------------------

def test_trend_apex_logistics_acute_risk_not_diluted():
    """
    Regression Test (Must Fix #1): Verify acute distress signals for Apex Logistics
    are not diluted to Low tier when neutral/routine headlines are present in the window.
    """
    acute_headline = "Apex Logistics files for bankruptcy and emergency restructuring following severe debt default."
    records = [
        {"date": "2026-03-22", "headline": acute_headline},
        {"date": "2026-03-10", "headline": "Apex Logistics continues routine warehouse inventory operations."},
        {"date": "2026-03-12", "headline": "Apex Logistics conducts annual fleet safety inspection."},
        {"date": "2026-03-15", "headline": "Apex Logistics maintains standard regional distribution routes."},
        {"date": "2026-03-18", "headline": "Apex Logistics publishes quarterly corporate logistics report."},
        {"date": "2026-03-20", "headline": "Apex Logistics participates in annual freight carrier conference."},
    ]

    res = calculate_supplier_trend("Apex Logistics", records)

    # Must remain elevated in Critical tier (>= 85.0) and NEVER diluted down to Low (< 60.0)
    assert res["current_risk_score"] >= 85.0, (
        f"Expected Apex Logistics acute risk score >= 85.0, got {res['current_risk_score']}"
    )
    assert res["current_window_article_count"] == 6
    # Verify top evidence captures the acute bankruptcy/default event
    top_headlines = [item["headline"] for item in res["top_evidence"]]
    assert acute_headline in top_headlines


def test_trend_apex_logistics_real_30_day_headlines_not_diluted():
    """
    Team Lead Review Regression Test (Round 9 M1 & Fix 1):
    Verify that calculating trend on Apex Logistics' headlines from the benchmark
    dataset produces a peak risk score across both windows (~60 days) in the Critical
    tier (>= 85.0) and that acute distress (bankruptcy/restructuring/shutdown)
    is preserved in peak_risk_score and top evidence.
    """
    from src.data import load_25_company_trend_dataset
    dataset = load_25_company_trend_dataset()
    apex_records = dataset["Apex Logistics"]

    res = calculate_supplier_trend("Apex Logistics", apex_records)

    # 1. Apex peak risk score across both windows (~60 days) remains in Critical tier (>= 85.0)
    assert res["peak_risk_score"] >= 85.0, (
        f"Expected Apex Logistics peak risk score >= 85.0 (Critical tier), "
        f"got {res['peak_risk_score']}"
    )
    assert res["peak_risk_tier"] == "Critical"
    assert res["current_risk_score"] > 60.0

    # 2. Window article count reflects active rolling window
    assert res["current_window_article_count"] > 0
    assert res["article_count"] == len(apex_records)

    # 3. Top evidence must contain the severe acute distress headlines
    assert len(res["top_evidence"]) > 0
    evidence_signals = [
        s["keyword"]
        for item in res["top_evidence"]
        for s in item.get("signals", [])
    ]
    assert any(sig in evidence_signals for sig in ["bankruptcy", "shutdown", "layoff", "default", "restructuring"])


def test_25_company_trend_anti_dilution_and_low_supplier_safeguards():
    """
    Round 9 M1 Validation Test:
    Verify across the 25-company trend dataset:
    1. Critical suppliers (e.g. Apex Logistics) maintain High/Critical peak window scores.
    2. Routine Low-tier suppliers (Siemens, ASML, Texas Instruments, Schneider Electric)
       remain with current_risk_score and peak_risk_score in the Low tier (< 60.0).
    3. Low tier suppliers do not trigger severe compliance deterioration actions.
    """
    from src.data import load_25_company_trend_dataset
    dataset = load_25_company_trend_dataset()

    # Apex Logistics peak window score must be High or Critical
    apex_res = calculate_supplier_trend("Apex Logistics", dataset["Apex Logistics"])
    assert apex_res["peak_risk_score"] >= 85.0
    assert apex_res["peak_risk_tier"] == "Critical"

    # Low suppliers must remain firmly in Low tier (< 60.0)
    low_suppliers = ["Siemens", "ASML", "Texas Instruments", "Schneider Electric"]
    for supp in low_suppliers:
        res = calculate_supplier_trend(supp, dataset[supp])
        assert res["current_risk_score"] < 60.0, (
            f"Expected {supp} current risk score < 60.0 (Low tier), got {res['current_risk_score']}"
        )
        assert res["peak_risk_tier"] == "Low"


def test_trend_as_of_date_historical_cutoff():
    """
    Must Fix #2: Verify as_of_date enforces a historical cutoff and excludes future articles.
    """
    records = [
        {"date": "2026-01-15", "headline": "SupplierCorp reports quarterly earnings."},
        {"date": "2026-02-15", "headline": "SupplierCorp faces supply disruption and delivery delay."},
        {"date": "2026-03-25", "headline": "SupplierCorp files for bankruptcy after fraud scandal."},
    ]

    # As of 2026-02-28, the March 25 article should be excluded from current window
    res = calculate_supplier_trend("SupplierCorp", records, as_of_date="2026-02-28")
    assert res["window_end"] == "2026-02-28"
    assert res["window_start"] == "2026-01-29"
    # March 25 article is in the future relative to cutoff
    assert res["current_window_article_count"] == 1
    # Current risk score reflects the Feb 15 disruption, NOT the March 25 bankruptcy
    assert res["current_risk_score"] < 80.0


def test_trend_as_of_date_omitted_defaults_to_latest():
    """
    Must Fix #2: Verify omitting as_of_date anchors to the latest available article date.
    """
    records = [
        {"date": "2026-01-10", "headline": "SupplierCorp holds shareholder meeting."},
        {"date": "2026-03-20", "headline": "SupplierCorp announces expansion into Asia."},
    ]

    res = calculate_supplier_trend("SupplierCorp", records)
    assert res["window_end"] == "2026-03-20"


def test_trend_as_of_date_later_than_data():
    """
    Must Fix #2: Verify as_of_date later than available data cleanly sets boundaries.
    """
    records = [
        {"date": "2026-01-10", "headline": "SupplierCorp holds shareholder meeting."},
    ]

    # as_of_date is 90 days after the only article
    res = calculate_supplier_trend("SupplierCorp", records, as_of_date="2026-04-10")
    assert res["window_end"] == "2026-04-10"
    assert res["window_start"] == "2026-03-11"
    assert res["current_window_article_count"] == 0
    assert res["current_risk_score"] == 0.0
    assert res["historical_article_count"] == 1


def test_trend_as_of_date_invalid_format():
    """
    Must Fix #2: Invalid date format in as_of_date raises ValueError.
    """
    records = [{"date": "2026-01-10", "headline": "SupplierCorp reports positive earnings."}]
    with pytest.raises(ValueError, match="Invalid calendar date"):
        calculate_supplier_trend("SupplierCorp", records, as_of_date="2026-99-99")


def test_api_trend_post_with_as_of_date():
    """
    Must Fix #2: POST /api/v1/supplier-risk/trend respects as_of_date in request body.
    """
    with TestClient(app) as client:
        payload = {
            "supplier_name": "CutoffSupplier",
            "articles": [
                {"date": "2026-02-10", "headline": "CutoffSupplier reports normal operations."},
                {"date": "2026-03-30", "headline": "CutoffSupplier faces severe strike and disruption."},
            ],
            "as_of_date": "2026-02-28",
        }
        response = client.post("/api/v1/supplier-risk/trend", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["window_end"] == "2026-02-28"
        assert data["current_window_article_count"] == 1


def test_api_trend_extra_fields_forbidden():
    """
    Must Fix #2: Extra unsupported fields in TrendAnalysisRequest must return 422.
    """
    with TestClient(app) as client:
        payload = {
            "supplier_name": "TestSupplier",
            "articles": [
                {"date": "2026-02-10", "headline": "TestSupplier reports normal operations."},
            ],
            "unsupported_field": "disallowed",
        }
        response = client.post("/api/v1/supplier-risk/trend", json=payload)
        assert response.status_code == 422


def test_api_predict_empty_headline_rejected():
    """
    Must Fix #2: Empty or whitespace-only headline in POST /predict must return 422.
    """
    with TestClient(app) as client:
        # Whitespace-only headline
        response = client.post("/predict", json={
            "supplier_name": "TestCorp",
            "headlines": ["   "],
        })
        assert response.status_code == 422

        # Empty string headline
        response = client.post("/predict", json={
            "supplier_name": "TestCorp",
            "headlines": [""],
        })
        assert response.status_code == 422


def test_api_trend_empty_headline_rejected():
    """
    Must Fix #2: Empty or whitespace-only headline in POST trend must return 422.
    """
    with TestClient(app) as client:
        response = client.post("/api/v1/supplier-risk/trend", json={
            "supplier_name": "TestCorp",
            "articles": [{"date": "2026-01-01", "headline": "   "}],
        })
        assert response.status_code == 422


def test_api_headline_max_length_validation():
    """
    Must Fix #2: Headline of 2000 chars passes, >2000 chars returns 422.
    """
    with TestClient(app) as client:
        valid_headline = "A" * 2000
        response = client.post("/predict", json={
            "supplier_name": "TestCorp",
            "headlines": [valid_headline],
        })
        assert response.status_code == 200

        too_long_headline = "A" * 2001
        response = client.post("/predict", json={
            "supplier_name": "TestCorp",
            "headlines": [too_long_headline],
        })
        assert response.status_code == 422


def test_trend_exact_30_day_rolling_window_boundary():
    """
    Verify exact 30-day rolling-window boundary:
    - Article exactly ref_date - 30 days is included in current window
    - Article ref_date - 31 days is excluded from current window / belongs to previous window
    """
    from datetime import datetime, timedelta

    ref_date_str = "2026-03-31"
    ref_d = datetime.strptime(ref_date_str, "%Y-%m-%d").date()
    d_30_days_ago = (ref_d - timedelta(days=30)).strftime("%Y-%m-%d")  # 2026-03-01
    d_31_days_ago = (ref_d - timedelta(days=31)).strftime("%Y-%m-%d")  # 2026-02-28

    records = [
        {"date": d_31_days_ago, "headline": "BoundaryCorp faces bankruptcy and default."},
        {"date": d_30_days_ago, "headline": "BoundaryCorp hit with strike and walkout."},
        {"date": ref_date_str, "headline": "BoundaryCorp reports positive earnings."},
    ]

    res = calculate_supplier_trend("BoundaryCorp", records, as_of_date=ref_date_str)

    # 1. Total articles evaluated
    assert res["article_count"] == 3
    # 2. Exactly 30-day article is included in current rolling window (total: 2 articles)
    assert res["current_window_article_count"] == 2
    # 3. Exactly 31-day article is excluded from current window and captured in previous window
    assert res["historical_article_count"] == 1
    # 4. Current window start is ref_date - 30 days
    assert res["window_end"] == ref_date_str
    assert res["window_start"] == d_30_days_ago
    # 5. Previous window score captures the 31-day bankruptcy event
    assert res["previous_risk_score"] is not None
    assert res["previous_risk_score"] > 50.0


def test_api_trend_article_headline_length_validation():
    """
    Verify TrendArticleInput headline length constraints via POST /api/v1/supplier-risk/trend:
    - 1-character headline succeeds (200)
    - exactly 2000-character headline succeeds (200)
    - 2001-character headline returns 422
    """
    with TestClient(app) as client:
        # 1-char headline
        resp_1 = client.post("/api/v1/supplier-risk/trend", json={
            "supplier_name": "LengthSupplier",
            "articles": [{"date": "2026-01-01", "headline": "A"}],
        })
        assert resp_1.status_code == 200

        # exactly 2000-char headline
        resp_2000 = client.post("/api/v1/supplier-risk/trend", json={
            "supplier_name": "LengthSupplier",
            "articles": [{"date": "2026-01-01", "headline": "A" * 2000}],
        })
        assert resp_2000.status_code == 200

        # 2001-char headline
        resp_2001 = client.post("/api/v1/supplier-risk/trend", json={
            "supplier_name": "LengthSupplier",
            "articles": [{"date": "2026-01-01", "headline": "A" * 2001}],
        })
        assert resp_2001.status_code == 422


def test_api_trend_missing_required_fields_rejected():
    """
    Verify POST /api/v1/supplier-risk/trend returns 422 when required top-level fields are missing:
    - missing supplier_name returns 422
    - missing articles returns 422
    """
    with TestClient(app) as client:
        # missing supplier_name
        resp_no_supplier = client.post("/api/v1/supplier-risk/trend", json={
            "articles": [{"date": "2026-01-01", "headline": "Valid headline."}],
        })
        assert resp_no_supplier.status_code == 422

        # missing articles
        resp_no_articles = client.post("/api/v1/supplier-risk/trend", json={
            "supplier_name": "TestSupplier",
        })
        assert resp_no_articles.status_code == 422


def test_api_trend_invalid_as_of_date_rejected():
    """
    Verify POST /api/v1/supplier-risk/trend with invalid as_of_date returns 422.
    """
    with TestClient(app) as client:
        response = client.post("/api/v1/supplier-risk/trend", json={
            "supplier_name": "TestSupplier",
            "articles": [{"date": "2026-01-01", "headline": "Valid headline."}],
            "as_of_date": "2026-99-99",
        })
        assert response.status_code == 422


def test_api_trend_non_string_headline_rejected():
    """
    Verify POST /api/v1/supplier-risk/trend with non-string headline returns 422.
    """
    with TestClient(app) as client:
        response = client.post("/api/v1/supplier-risk/trend", json={
            "supplier_name": "TestSupplier",
            "articles": [{"date": "2026-01-01", "headline": 12345}],
        })
        assert response.status_code == 422


def test_api_trend_too_many_articles_rejected():
    """
    Verify POST /api/v1/supplier-risk/trend with >100 articles returns 422.
    """
    with TestClient(app) as client:
        articles = [{"date": "2026-01-01", "headline": f"Headline {i}"} for i in range(101)]
        response = client.post("/api/v1/supplier-risk/trend", json={
            "supplier_name": "TestSupplier",
            "articles": articles,
        })
        assert response.status_code == 422


def test_api_get_trend_with_as_of_date_query_param():
    """
    Verify GET /api/v1/supplier-risk/trend/{supplier_name}?as_of_date=YYYY-MM-DD:
    - valid as_of_date is accepted and sets the window cutoff
    - invalid as_of_date returns 422 validation error
    """
    with TestClient(app) as client:
        # Valid as_of_date
        resp_valid = client.get("/api/v1/supplier-risk/trend/Tesla?as_of_date=2026-01-15")
        assert resp_valid.status_code == 200
        data = resp_valid.json()
        assert data["supplier"] == "Tesla"
        assert data["window_end"] == "2026-01-15"

        # Invalid as_of_date format
        resp_invalid = client.get("/api/v1/supplier-risk/trend/Tesla?as_of_date=not-a-valid-date")
        assert resp_invalid.status_code == 422

        # Invalid calendar date
        resp_bad_date = client.get("/api/v1/supplier-risk/trend/Tesla?as_of_date=2026-02-30")
        assert resp_bad_date.status_code == 422


# ------------------------------------------------------------------
# 8. Team Lead FIX 1: Trend Scoring & Peak Window Tier Tests
# ------------------------------------------------------------------

def test_trend_window_score_uses_predict_aggregation():
    """Prove trend window score uses predict() aggregation directly."""
    from src.predict import predict
    supplier = "Beta Corp"
    records = [
        {"date": "2026-03-10", "headline": "Beta Corp faces severe supply disruption."},
        {"date": "2026-03-20", "headline": "Beta Corp hit with major recall due to defect."},
    ]
    res = calculate_supplier_trend(supplier, records)
    direct_predict = predict(supplier, [r["headline"] for r in records])
    assert res["current_risk_score"] == round(float(direct_predict["risk_score"]), 2)


def test_trend_no_recency_decay_inside_window():
    """Prove recency decay is NOT applied inside a window."""
    # Two identical-severity events placed at different times within the same 30-day window
    records_recent_bad = [
        {"date": "2026-03-02", "headline": "Beta Corp reports positive earnings and strong demand."},
        {"date": "2026-03-30", "headline": "Beta Corp hit with severe sanction and product recall."},
    ]
    records_old_bad = [
        {"date": "2026-03-02", "headline": "Beta Corp hit with severe sanction and product recall."},
        {"date": "2026-03-30", "headline": "Beta Corp reports positive earnings and strong demand."},
    ]
    res_recent_bad = calculate_supplier_trend("Beta Corp", records_recent_bad)
    res_old_bad = calculate_supplier_trend("Beta Corp", records_old_bad)
    assert res_recent_bad["current_risk_score"] == res_old_bad["current_risk_score"]


def test_trend_current_and_previous_tiers_returned():
    """Prove current and previous risk tiers are returned and match assign_risk_tier."""
    from src.evaluate import assign_risk_tier
    records = [
        {"date": "2026-01-15", "headline": "Alpha Corp reports positive earnings and strong demand."},
        {"date": "2026-03-20", "headline": "Alpha Corp hit with severe strike and production disruption."},
    ]
    res = calculate_supplier_trend("Alpha Corp", records)
    assert "current_risk_tier" in res
    assert "previous_risk_tier" in res
    assert res["current_risk_tier"] == assign_risk_tier(res["current_risk_score"])
    assert res["previous_risk_tier"] == assign_risk_tier(res["previous_risk_score"])


def test_trend_peak_risk_score_is_max_current_previous():
    """Prove peak_risk_score is max(current, previous)."""
    # Case 1: current > previous
    records_rising = [
        {"date": "2026-01-15", "headline": "Alpha Corp reports positive earnings."},
        {"date": "2026-03-20", "headline": "Alpha Corp hit with severe strike and default."},
    ]
    res_rising = calculate_supplier_trend("Alpha Corp", records_rising)
    assert res_rising["current_risk_score"] > res_rising["previous_risk_score"]
    assert res_rising["peak_risk_score"] == res_rising["current_risk_score"]

    # Case 2: previous > current
    records_falling = [
        {"date": "2026-01-15", "headline": "Alpha Corp hit with severe strike and default."},
        {"date": "2026-03-20", "headline": "Alpha Corp reports positive earnings."},
    ]
    res_falling = calculate_supplier_trend("Alpha Corp", records_falling)
    assert res_falling["previous_risk_score"] > res_falling["current_risk_score"]
    assert res_falling["peak_risk_score"] == res_falling["previous_risk_score"]


def test_trend_peak_risk_tier_matches_peak_risk_score():
    """Prove peak_risk_tier matches peak_risk_score."""
    from src.evaluate import assign_risk_tier
    records = [
        {"date": "2026-01-15", "headline": "Gamma Corp declares bankruptcy and emergency restructuring."},
        {"date": "2026-03-20", "headline": "Gamma Corp reports routine administrative meeting."},
    ]
    res = calculate_supplier_trend("Gamma Corp", records)
    assert res["peak_risk_tier"] == assign_risk_tier(res["peak_risk_score"])


def test_trend_low_to_low_rise_not_deterioration():
    """Prove Low -> Low score increase is NOT flagged as deterioration."""
    # Both in Low tier (< 60.0), delta > 3.0
    with patch("src.trend.predict") as mock_p:
        mock_p.side_effect = lambda supplier_name, headlines, config=None: {
            "supplier": supplier_name,
            "risk_score": 50.0 if "current" in headlines[0] else 40.0,
            "confidence": 0.8,
            "sentiment_breakdown": {},
            "signals": [],
            "top_worst_3": [],
        }
        records = [
            {"date": "2026-01-15", "headline": "previous headline"},
            {"date": "2026-03-20", "headline": "current headline"},
        ]
        res = calculate_supplier_trend("LowCorp", records)
        assert res["current_risk_tier"] == "Low"
        assert res["previous_risk_tier"] == "Low"
        assert res["risk_delta"] == 10.0
        assert res["trend_direction"] == "rising"
        assert res["is_deteriorating"] is False
        assert "not flagged as deteriorating" in res["deterioration_summary"]


def test_trend_medium_to_medium_rise_not_deterioration():
    """Prove Medium -> Medium score increase is NOT flagged as deterioration."""
    # Both in Medium tier (60.0 <= score < 72.0), delta > 3.0
    with patch("src.trend.predict") as mock_p:
        mock_p.side_effect = lambda supplier_name, headlines, config=None: {
            "supplier": supplier_name,
            "risk_score": 68.0 if "current" in headlines[0] else 62.0,
            "confidence": 0.8,
            "sentiment_breakdown": {},
            "signals": [],
            "top_worst_3": [],
        }
        records = [
            {"date": "2026-01-15", "headline": "previous headline"},
            {"date": "2026-03-20", "headline": "current headline"},
        ]
        res = calculate_supplier_trend("MedCorp", records)
        assert res["current_risk_tier"] == "Medium"
        assert res["previous_risk_tier"] == "Medium"
        assert res["risk_delta"] == 6.0
        assert res["trend_direction"] == "rising"
        assert res["is_deteriorating"] is False
        assert "not flagged as deteriorating" in res["deterioration_summary"]


def test_trend_low_to_medium_rise_is_deterioration():
    """Prove Low -> Medium rise (tier worsened) IS flagged as deterioration."""
    with patch("src.trend.predict") as mock_p:
        mock_p.side_effect = lambda supplier_name, headlines, config=None: {
            "supplier": supplier_name,
            "risk_score": 65.0 if "current" in headlines[0] else 50.0,
            "confidence": 0.8,
            "sentiment_breakdown": {},
            "signals": [],
            "top_worst_3": [],
        }
        records = [
            {"date": "2026-01-15", "headline": "previous headline"},
            {"date": "2026-03-20", "headline": "current headline"},
        ]
        res = calculate_supplier_trend("WorseningCorp", records)
        assert res["current_risk_tier"] == "Medium"
        assert res["previous_risk_tier"] == "Low"
        assert res["trend_direction"] == "rising"
        assert res["is_deteriorating"] is True
        assert "Risk is deteriorating" in res["deterioration_summary"]


def test_trend_medium_to_high_rise_is_deterioration():
    """Prove Medium -> High rise (tier worsened) IS flagged as deterioration."""
    with patch("src.trend.predict") as mock_p:
        mock_p.side_effect = lambda supplier_name, headlines, config=None: {
            "supplier": supplier_name,
            "risk_score": 76.0 if "current" in headlines[0] else 65.0,
            "confidence": 0.8,
            "sentiment_breakdown": {},
            "signals": [],
            "top_worst_3": [],
        }
        records = [
            {"date": "2026-01-15", "headline": "previous headline"},
            {"date": "2026-03-20", "headline": "current headline"},
        ]
        res = calculate_supplier_trend("WorseningCorp", records)
        assert res["current_risk_tier"] == "High"
        assert res["previous_risk_tier"] == "Medium"
        assert res["trend_direction"] == "rising"
        assert res["is_deteriorating"] is True
        assert "Risk is deteriorating" in res["deterioration_summary"]


def test_trend_high_critical_rise_is_deterioration():
    """Prove score increase when already High or Critical IS flagged as deterioration."""
    # High -> High rise (already elevated)
    with patch("src.trend.predict") as mock_p:
        mock_p.side_effect = lambda supplier_name, headlines, config=None: {
            "supplier": supplier_name,
            "risk_score": 82.0 if "current" in headlines[0] else 74.0,
            "confidence": 0.8,
            "sentiment_breakdown": {},
            "signals": [],
            "top_worst_3": [],
        }
        records = [
            {"date": "2026-01-15", "headline": "previous headline"},
            {"date": "2026-03-20", "headline": "current headline"},
        ]
        res = calculate_supplier_trend("HighCorp", records)
        assert res["current_risk_tier"] == "High"
        assert res["previous_risk_tier"] == "High"
        assert res["trend_direction"] == "rising"
        assert res["is_deteriorating"] is True

    # Critical -> Critical rise (already elevated)
    with patch("src.trend.predict") as mock_p:
        mock_p.side_effect = lambda supplier_name, headlines, config=None: {
            "supplier": supplier_name,
            "risk_score": 95.0 if "current" in headlines[0] else 87.0,
            "confidence": 0.8,
            "sentiment_breakdown": {},
            "signals": [],
            "top_worst_3": [],
        }
        res_crit = calculate_supplier_trend("CritCorp", records)
        assert res_crit["current_risk_tier"] == "Critical"
        assert res_crit["previous_risk_tier"] == "Critical"
        assert res_crit["trend_direction"] == "rising"
        assert res_crit["is_deteriorating"] is True


def test_trend_no_history_response():
    """Prove no-history response has expected tier and peak fields."""
    records = [
        {"date": "2026-03-20", "headline": "SoloCorp reports positive earnings."},
    ]
    res = calculate_supplier_trend("SoloCorp", records)
    assert res["previous_risk_score"] is None
    assert res["previous_risk_tier"] is None
    assert res["peak_risk_score"] == res["current_risk_score"]
    assert res["peak_risk_tier"] == res["current_risk_tier"]


# ------------------------------------------------------------------
# 9. Team Lead FIX 2: As-Of-Date Filtering & Future-Data Leakage Tests
# ------------------------------------------------------------------

def test_trend_future_articles_do_not_leak_into_outputs():
    """
    Must Fix #2: Future articles past as_of_date must NOT leak into:
    - article_count
    - current_risk_score
    - top_evidence
    - risk_trend
    - overall_confidence
    """
    past_records = [
        {"date": "2026-01-10", "headline": "SupplierCorp faces supply chain delays."},
        {"date": "2026-02-15", "headline": "SupplierCorp signs major distribution agreement."},
    ]
    future_records = [
        {"date": "2026-03-10", "headline": "SupplierCorp hit by catastrophic factory explosion and bankruptcy scandal."},
        {"date": "2026-04-05", "headline": "SupplierCorp executive arrested for widespread fraud."},
    ]
    all_records = past_records + future_records

    cutoff = "2026-02-28"
    res_past = calculate_supplier_trend("SupplierCorp", past_records, as_of_date=cutoff)
    res_all = calculate_supplier_trend("SupplierCorp", all_records, as_of_date=cutoff)

    # 1. article_count: exactly equals past articles count, future articles excluded
    assert res_all["article_count"] == res_past["article_count"] == 2

    # 2. current_risk_score: identical to past-only run; catastrophic future events do NOT inflate score
    assert res_all["current_risk_score"] == res_past["current_risk_score"]

    # 3. top_evidence: identical to past-only run; no future headlines in top evidence
    assert res_all["top_evidence"] == res_past["top_evidence"]
    future_headline_texts = {r["headline"].lower() for r in future_records}
    for ev in res_all["top_evidence"]:
        assert ev["headline"].lower() not in future_headline_texts

    # 4. risk_trend: identical chronological points to past-only run; no future dates exist
    assert res_all["risk_trend"] == res_past["risk_trend"]
    for point in res_all["risk_trend"]:
        assert point["date"] <= cutoff

    # 5. overall_confidence: identical to past-only run; future articles do not weight or alter confidence
    assert res_all["overall_confidence"] == res_past["overall_confidence"]


def test_trend_exact_cutoff_date_included():
    """Must Fix #2: Exact cutoff date (d == ref_date) is INCLUDED in trend evaluation."""
    cutoff = "2026-02-28"
    records = [
        {"date": "2026-02-15", "headline": "SupplierCorp reports steady quarter."},
        {"date": "2026-02-28", "headline": "SupplierCorp suffers severe operational shutdown."},
        {"date": "2026-03-01", "headline": "SupplierCorp resumes partial operations."},
    ]
    res = calculate_supplier_trend("SupplierCorp", records, as_of_date=cutoff)

    # 2026-02-15 and 2026-02-28 included; 2026-03-01 excluded
    assert res["article_count"] == 2
    trend_dates = [p["date"] for p in res["risk_trend"]]
    assert "2026-02-28" in trend_dates
    assert "2026-03-01" not in trend_dates

    # The exact cutoff headline appears in evidence
    evidence_headlines = [e["headline"] for e in res["top_evidence"]]
    assert any("severe operational shutdown" in h for h in evidence_headlines)


def test_trend_all_future_articles_returns_empty_response():
    """Must Fix #2: When all records are in the future, return exact empty response."""
    records = [
        {"date": "2026-04-01", "headline": "SupplierCorp hit by severe factory strike."},
        {"date": "2026-05-15", "headline": "SupplierCorp defaults on debt obligation."},
    ]
    res = calculate_supplier_trend("SupplierCorp", records, as_of_date="2026-03-15")

    assert res["article_count"] == 0
    assert res["current_window_article_count"] == 0
    assert res["historical_article_count"] == 0
    assert res["current_risk_score"] == 0.0
    assert res["previous_risk_score"] is None
    assert res["current_risk_tier"] == "Low"
    assert res["previous_risk_tier"] is None
    assert res["peak_risk_score"] == 0.0
    assert res["peak_risk_tier"] == "Low"
    assert res["trend_direction"] == "stable"
    assert res["is_deteriorating"] is False
    assert res["risk_delta"] is None
    assert res["overall_confidence"] == 0.0
    assert res["top_evidence"] == []
    assert res["risk_trend"] == []


def test_trend_window_start_uses_cutoff_and_window_end_equals_cutoff():
    """Must Fix #2: window_end equals cutoff and window_start is cutoff - window_days."""
    cutoff = "2026-03-15"
    records = [
        {"date": "2026-02-01", "headline": "SupplierCorp historical notice."},
        {"date": "2026-03-01", "headline": "SupplierCorp recent update."},
    ]
    res = calculate_supplier_trend("SupplierCorp", records, as_of_date=cutoff)

    assert res["window_end"] == cutoff
    assert res["window_start"] == "2026-02-13"  # 2026-03-15 minus 30 days


def test_trend_omitted_as_of_date_preserves_behavior():
    """Must Fix #2: Omitted as_of_date anchors to max(date_objs) and preserves behavior."""
    records = [
        {"date": "2026-01-10", "headline": "SupplierCorp January report."},
        {"date": "2026-02-20", "headline": "SupplierCorp February report."},
        {"date": "2026-03-25", "headline": "SupplierCorp March report."},
    ]
    res_omitted = calculate_supplier_trend("SupplierCorp", records)
    res_none = calculate_supplier_trend("SupplierCorp", records, as_of_date=None)

    assert res_omitted["window_end"] == "2026-03-25"
    assert res_none["window_end"] == "2026-03-25"
    assert res_omitted["article_count"] == 3
    assert res_none["article_count"] == 3
    assert res_omitted == res_none


def test_as_of_date_excludes_later_articles_everywhere():
    records = [
        {
            "date": "2026-01-15",
            "headline": "SupplierCorp reports quarterly earnings.",
        },
        {
            "date": "2026-02-15",
            "headline": "SupplierCorp faces supply disruption and delivery delay.",
        },
        {
            "date": "2026-03-25",
            "headline": "SupplierCorp files for bankruptcy after fraud scandal.",
        },
    ]

    res = calculate_supplier_trend(
        "SupplierCorp",
        records,
        as_of_date="2026-02-28",
    )

    assert res["article_count"] == 2
    assert all(
        point["date"] <= "2026-02-28"
        for point in res["risk_trend"]
    )
    assert all(
        "bankruptcy" not in e["headline"].lower()
        for e in res["top_evidence"]
    )


def test_as_of_date_before_all_articles_returns_empty():
    records = [
        {
            "date": "2026-03-25",
            "headline": "SupplierCorp files for bankruptcy.",
        }
    ]

    res = calculate_supplier_trend(
        "SupplierCorp",
        records,
        as_of_date="2025-01-01",
    )

    assert res["article_count"] == 0
    assert res["top_evidence"] == []
    assert res["risk_trend"] == []
    assert res["window_end"] == "2025-01-01"
