"""
Comprehensive synthetic test suite for Issue #350 [R15-M7]:
Supplier Risk Scoring on Client Supplier Format.

Verifies all 25 required test scenarios:
 1. Supplier with valid master data and multiple incidents.
 2. Supplier with no incidents.
 3. Supplier with missing on-time delivery percentage.
 4. Supplier with on-time percentage available.
 5. Supplier with Quality incidents.
 6. Supplier with Delay incidents.
 7. Supplier with Dispute incidents.
 8. Supplier with Other incidents.
 9. Incident dated in the future must be excluded.
10. Incident older than 12 months must be excluded from the 12-month count.
11. Days since last incident calculation.
12. Supplier identified using supplier_code.
13. Supplier identified using canonical supplier_id.
14. Unknown supplier mapping.
15. Invalid incident type.
16. Invalid or missing incident date.
17. Missing optional fields.
18. MongoDB/data-loading failure.
19. Cached assessment with new fields.
20. Old cached assessment without new fields.
21. Existing API authentication tests.
22. Existing endpoint aliases.
23. Existing no-evidence behavior.
24. Existing sanctions behavior.
25. Existing NLP scoring tests.
"""

import csv
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from pymongo.errors import PyMongoError
import yaml

from src.analyze import (
    SupplierRiskScoreResponse,
    _save_assessment,
    app,
    compute_canonical_supplier_risk_score,
    require_caller,
)
from src.client_supplier import (
    ClientRiskFeatures,
    ClientSupplierMaster,
    SupplierIncident,
    calculate_client_risk_features,
    calculate_client_risk_score,
    generate_top_reasons,
    resolve_supplier_code_to_canonical_id,
    save_client_supplier_master,
    save_supplier_incidents_data,
    validate_incident_date,
    validate_incident_type,
)
from src.client_supplier import normalize_incident_type
from src.config import (
    Settings,
    get_settings,
    validate_composite_weights,
    validate_factor_weight,
)
from src.db import (
    fetch_client_incidents,
    fetch_client_supplier,
    save_client_incident,
    save_client_supplier,
)
from src.evaluate import assign_risk_tier


REPO_ROOT = Path(__file__).resolve().parents[3]

CLIENT_SAMPLES = (
    REPO_ROOT
    / "data-platform"
    / "etl"
    / "client_ingest"
    / "samples"
    / "client_format"
)


# Test client fixture that bypasses Platform JWT check
VALID_SERVICE_CONFIG = "supplier-portal:valid-secret-key,inventory-service:inv-key-999"
VALID_SERVICE_HEADERS = {
    "X-Caller-Service": "supplier-portal",
    "X-Service-Key": "valid-secret-key",
}


@pytest.fixture(autouse=True)
def default_auth_env(monkeypatch):
    """Set standard service keys for API tests so general endpoint assertions succeed."""
    monkeypatch.setenv("SUPPLIER_RISK_SERVICE_KEYS", VALID_SERVICE_CONFIG)


@pytest.fixture(autouse=True)
def mock_sentiment():
    """Mock FinBERT model initialization and sentiment to avoid test latency and missing model weight downloads."""
    with patch("src.predict.analyze_sentiment") as mock_sa, \
         patch("src.analyze.init_model") as mock_im:
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
        mock_sa.side_effect = side_effect
        yield mock_sa, mock_im


@pytest.fixture
def auth_client():
    app.dependency_overrides[require_caller] = lambda: "test-caller"
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(require_caller, None)


# Raw test client fixture exercising full authentication
@pytest.fixture
def unauth_client():
    saved = app.dependency_overrides.pop(require_caller, None)
    with TestClient(app) as test_client:
        yield test_client
    if saved is not None:
        app.dependency_overrides[require_caller] = saved


# -----------------------------------------------------------------------------
# Scenario 1: Supplier with valid master data and multiple incidents
# -----------------------------------------------------------------------------
def test_scenario_01_valid_master_multiple_incidents(fake_supplier_store):
    """Scenario 1: Supplier with valid master data and multiple incidents across types."""
    # Seed canonical mapping
    fake_supplier_store.suppliers.insert_one({
        "supplier_id": "SUP-91001",
        "name": "Synthetic Multi Incident Corp",
        "normalized_name": "synthetic multi incident corp",
        "sanctions_flag": False,
    })

    master = {
        "supplier_id": "SUP-91001",
        "legal_name": "Synthetic Multi Incident Corp",
        "country": "India",
        "city": "Bengaluru",
        "category": "Raw Materials",
        "on_time_delivery_pct": 91.5,
    }
    save_client_supplier(master)

    scoring_date = "2026-10-15"
    incidents = [
        {"supplier_id": "SUP-91001", "incident_date": "2026-09-01", "incident_type": "Delay", "description": "Border delay"},
        {"supplier_id": "SUP-91001", "incident_date": "2026-08-15", "incident_type": "Delay", "description": "Port delay"},
        {"supplier_id": "SUP-91001", "incident_date": "2026-07-20", "incident_type": "Quality", "description": "Batch defect"},
        {"supplier_id": "SUP-91001", "incident_date": "2026-05-10", "incident_type": "Dispute", "description": "Invoice dispute"},
    ]
    for inc in incidents:
        save_client_incident(inc)

    features = calculate_client_risk_features(master, incidents, scoring_date=scoring_date)
    assert features.delay_incidents_12m == 2
    assert features.quality_incidents_12m == 1
    assert features.dispute_incidents_12m == 1
    assert features.other_incidents_12m == 0
    assert features.days_since_last_incident == 44  # 2026-10-15 - 2026-09-01
    assert features.on_time_delivery_pct == 91.5
    assert features.on_time_delivery_missing is False

    score = calculate_client_risk_score(features)
    assert score > 0.0

    reasons = generate_top_reasons(features)
    assert len(reasons) == 3
    assert any("delay incident" in r for r in reasons)
    assert any("quality incident" in r for r in reasons)


# -----------------------------------------------------------------------------
# Scenario 2: Supplier with no incidents
# -----------------------------------------------------------------------------
def test_scenario_02_supplier_with_no_incidents(fake_supplier_store):
    """Scenario 2: Supplier with valid master data and 0 recorded incidents."""
    master = {
        "supplier_id": "SUP-91002",
        "legal_name": "Zero Incident Industries",
        "country": "Germany",
        "city": "Stuttgart",
        "category": "Precision Tools",
        "on_time_delivery_pct": 98.0,
    }
    save_client_supplier(master)

    features = calculate_client_risk_features(master, [], scoring_date="2026-10-15")
    assert features.quality_incidents_12m == 0
    assert features.delay_incidents_12m == 0
    assert features.dispute_incidents_12m == 0
    assert features.other_incidents_12m == 0
    assert features.days_since_last_incident is None
    assert features.on_time_delivery_pct == 98.0
    assert features.on_time_delivery_missing is False

    score = calculate_client_risk_score(features)
    assert score == 0.0  # Clean operational baseline

    reasons = generate_top_reasons(features)
    assert "0 incidents reported in the last 12 months" in reasons


# -----------------------------------------------------------------------------
# Scenario 3: Supplier with missing on-time delivery percentage
# -----------------------------------------------------------------------------
def test_scenario_03_missing_on_time_delivery_pct(fake_supplier_store, caplog):
    """Scenario 3: Missing on-time delivery percentage must not be penalized as zero."""
    master = {
        "supplier_id": "SUP-91003",
        "legal_name": "Missing Delivery Co",
        "country": "Japan",
        "city": "Osaka",
        "category": "Electronics",
        "on_time_delivery_pct": None,  # Omitted
    }
    save_client_supplier(master)

    with caplog.at_level("DEBUG"):
        features = calculate_client_risk_features(master, [], scoring_date="2026-10-15")

    assert features.on_time_delivery_pct is None
    assert features.on_time_delivery_missing is True
    # Verify TODO #325 is documented and scoring continues
    assert features.quality_incidents_12m == 0
    score = calculate_client_risk_score(features)
    assert score == 0.0  # Must not penalize missing delivery as 0% late

    reasons = generate_top_reasons(features)
    assert any("Issue #325" in r or "missing" in r for r in reasons)


# -----------------------------------------------------------------------------
# Scenario 4: Supplier with on-time percentage available
# -----------------------------------------------------------------------------
def test_scenario_04_on_time_percentage_available(fake_supplier_store):
    """Scenario 4: Valid on-time percentage is reflected in features, score, and reasons."""
    master = {
        "supplier_id": "SUP-91004",
        "legal_name": "Punctual Parts Ltd",
        "country": "India",
        "city": "Chennai",
        "category": "Automotive",
        "on_time_delivery_pct": 99.2,
    }
    features = calculate_client_risk_features(master, [], scoring_date="2026-10-15")
    assert features.on_time_delivery_pct == 99.2
    assert features.on_time_delivery_missing is False

    reasons = generate_top_reasons(features)
    assert any("99.2%" in r for r in reasons)


# -----------------------------------------------------------------------------
# Scenario 5: Supplier with Quality incidents
# -----------------------------------------------------------------------------
def test_scenario_05_supplier_with_quality_incidents(fake_supplier_store):
    """Scenario 5: Quality incidents are counted and highlighted in features and reasons."""
    master = {
        "supplier_id": "SUP-91005",
        "legal_name": "Quality Focus Inc",
        "country": "USA",
        "city": "Detroit",
        "category": "Components",
    }
    incidents = [
        {"supplier_id": "SUP-91005", "incident_date": "2026-08-01", "incident_type": "Quality", "description": "Defective weld"},
        {"supplier_id": "SUP-91005", "incident_date": "2026-06-15", "incident_type": "Quality", "description": "Contamination detected"},
    ]
    features = calculate_client_risk_features(master, incidents, scoring_date="2026-10-15")
    assert features.quality_incidents_12m == 2
    assert features.delay_incidents_12m == 0

    reasons = generate_top_reasons(features)
    assert "2 quality incidents in 12 months" in reasons


# -----------------------------------------------------------------------------
# Scenario 6: Supplier with Delay incidents
# -----------------------------------------------------------------------------
def test_scenario_06_supplier_with_delay_incidents(fake_supplier_store):
    """Scenario 6: Delay incidents are counted and ground reasons like '4 delay incidents in 12 months'."""
    master = {
        "supplier_id": "SUP-91006",
        "legal_name": "Delayed Logistics AG",
        "country": "Switzerland",
        "city": "Basel",
        "category": "Freight",
    }
    incidents = [
        {"supplier_id": "SUP-91006", "incident_date": "2026-09-10", "incident_type": "Delay", "description": "Vessel late"},
        {"supplier_id": "SUP-91006", "incident_date": "2026-08-20", "incident_type": "Delay", "description": "Customs hold"},
        {"supplier_id": "SUP-91006", "incident_date": "2026-07-05", "incident_type": "Delay", "description": "Rail strike delay"},
        {"supplier_id": "SUP-91006", "incident_date": "2026-06-01", "incident_type": "Delay", "description": "Port congestion"},
    ]
    features = calculate_client_risk_features(master, incidents, scoring_date="2026-10-15")
    assert features.delay_incidents_12m == 4

    reasons = generate_top_reasons(features)
    assert "4 delay incidents in 12 months" in reasons


# -----------------------------------------------------------------------------
# Scenario 7: Supplier with Dispute incidents
# -----------------------------------------------------------------------------
def test_scenario_07_supplier_with_dispute_incidents(fake_supplier_store):
    """Scenario 7: Dispute incidents are tracked and categorized."""
    master = {
        "supplier_id": "SUP-91007",
        "legal_name": "Dispute Heavy Corp",
        "country": "UK",
        "city": "London",
        "category": "Services",
    }
    incidents = [
        {"supplier_id": "SUP-91007", "incident_date": "2026-05-01", "incident_type": "Dispute", "description": "SLA penalty dispute"},
        {"supplier_id": "SUP-91007", "incident_date": "2026-03-15", "incident_type": "Dispute", "description": "Pricing disagreement"},
    ]
    features = calculate_client_risk_features(master, incidents, scoring_date="2026-10-15")
    assert features.dispute_incidents_12m == 2

    reasons = generate_top_reasons(features)
    assert "2 dispute incidents in 12 months" in reasons


# -----------------------------------------------------------------------------
# Scenario 8: Supplier with Other incidents
# -----------------------------------------------------------------------------
def test_scenario_08_supplier_with_other_incidents(fake_supplier_store):
    """Scenario 8: Other incidents are counted and categorized as Operational."""
    master = {
        "supplier_id": "SUP-91008",
        "legal_name": "Misc Risk Supplies",
        "country": "India",
        "city": "Pune",
        "category": "Packaging",
    }
    incidents = [
        {"supplier_id": "SUP-91008", "incident_date": "2026-09-15", "incident_type": "Other", "description": "Packaging tear"},
    ]
    features = calculate_client_risk_features(master, incidents, scoring_date="2026-10-15")
    assert features.other_incidents_12m == 1

    reasons = generate_top_reasons(features)
    assert "1 other incident in 12 months" in reasons


# -----------------------------------------------------------------------------
# Scenario 9: Incident dated in the future must be excluded
# -----------------------------------------------------------------------------
def test_scenario_09_future_incident_must_be_excluded(fake_supplier_store):
    """Scenario 9: Future incidents after scoring_date are excluded from 12m counts and days_since."""
    master = {
        "supplier_id": "SUP-91009",
        "legal_name": "Future Incident Corp",
        "country": "India",
        "city": "Hyderabad",
        "category": "Semiconductors",
    }
    scoring_date = "2026-10-15"
    incidents = [
        {"supplier_id": "SUP-91009", "incident_date": "2026-10-10", "incident_type": "Delay", "description": "Valid past incident"},
        {"supplier_id": "SUP-91009", "incident_date": "2026-11-01", "incident_type": "Quality", "description": "Future incident"},
        {"supplier_id": "SUP-91009", "incident_date": "2027-01-15", "incident_type": "Delay", "description": "Far future incident"},
    ]
    features = calculate_client_risk_features(master, incidents, scoring_date=scoring_date)
    assert features.delay_incidents_12m == 1
    assert features.quality_incidents_12m == 0  # Future quality incident ignored
    assert features.days_since_last_incident == 5  # 2026-10-15 - 2026-10-10 (not future)


# -----------------------------------------------------------------------------
# Scenario 10: Incident older than 12 months excluded from 12-month count
# -----------------------------------------------------------------------------
def test_scenario_10_older_incident_excluded_from_12m_count(fake_supplier_store):
    """Scenario 10: Incident older than 365 days is excluded from 12m counts but counts for days_since."""
    master = {
        "supplier_id": "SUP-91010",
        "legal_name": "Old Incident Corp",
        "country": "India",
        "city": "Mumbai",
        "category": "Chemicals",
    }
    scoring_date = "2026-10-15"
    incidents = [
        # 410 days old incident
        {"supplier_id": "SUP-91010", "incident_date": "2025-09-01", "incident_type": "Delay", "description": "Old delay"},
    ]
    features = calculate_client_risk_features(master, incidents, scoring_date=scoring_date)
    assert features.delay_incidents_12m == 0  # Excluded from 12m count
    assert features.days_since_last_incident == 409  # Eligible for historical recency


# -----------------------------------------------------------------------------
# Scenario 11: Days since last incident calculation
# -----------------------------------------------------------------------------
def test_scenario_11_days_since_last_incident_calculation(fake_supplier_store):
    """Scenario 11: Days since last eligible incident must equal scoring_date minus latest eligible incident."""
    master = {"supplier_id": "SUP-91011", "legal_name": "Days Calc Corp", "country": "France", "city": "Paris", "category": "Logistics"}
    scoring_date = "2026-10-15"
    incidents = [
        {"supplier_id": "SUP-91011", "incident_date": "2026-08-01", "incident_type": "Other", "description": "Earlier"},
        {"supplier_id": "SUP-91011", "incident_date": "2026-10-05", "incident_type": "Delay", "description": "Latest"},
    ]
    features = calculate_client_risk_features(master, incidents, scoring_date=scoring_date)
    assert features.days_since_last_incident == 10  # 2026-10-15 - 2026-10-05


# -----------------------------------------------------------------------------
# Scenario 12: Supplier identified using supplier_code
# -----------------------------------------------------------------------------
def test_scenario_12_supplier_identified_by_supplier_code(auth_client, fake_supplier_store):
    """Scenario 12: Supplier identified using client supplier_code resolves to canonical ID."""
    fake_supplier_store.suppliers.insert_one({
        "supplier_id": "SUP-91012",
        "name": "Supplier Code Resolved Corp",
        "normalized_name": "supplier code resolved corp",
        "sanctions_flag": False,
        "supplier_codes": ["SUP-2231"],
    })
    save_client_supplier({
        "supplier_code": "SUP-2231",
        "supplier_id": "SUP-91012",
        "legal_name": "Supplier Code Resolved Corp",
        "country": "India",
        "city": "Hyderabad",
        "category": "IT Hardware",
        "on_time_delivery_pct": 95.0,
    })
    save_client_incident({
        "supplier_code": "SUP-2231",
        "incident_date": "2026-09-01",
        "incident_type": "Delay",
        "description": "Port delay",
    })

    # Query using client-suppliers endpoint
    res = auth_client.get(
        "/api/v1/supplier-risk/client-suppliers/SUP-2231/risk-score?as_of_date=2026-10-15"
    )
    assert res.status_code == 200
    data = res.json()
    assert data["supplier_id"] == "SUP-91012"
    assert data["client_risk_features"] is not None
    assert data["client_risk_features"]["delay_incidents_12m"] == 1


# -----------------------------------------------------------------------------
# Scenario 13: Supplier identified using canonical supplier_id
# -----------------------------------------------------------------------------
def test_scenario_13_supplier_identified_by_canonical_supplier_id(auth_client, fake_supplier_store):
    """Scenario 13: Supplier identified directly by canonical SUP-XXXXX identifier."""
    fake_supplier_store.suppliers.insert_one({
        "supplier_id": "SUP-91013",
        "name": "Canonical Direct Corp",
        "normalized_name": "canonical direct corp",
        "sanctions_flag": False,
    })
    save_client_supplier({
        "supplier_id": "SUP-91013",
        "legal_name": "Canonical Direct Corp",
        "country": "India",
        "city": "Bengaluru",
        "category": "Aerospace",
        "on_time_delivery_pct": 96.0,
    })
    res = auth_client.get("/api/v1/suppliers/SUP-91013/risk-score")
    assert res.status_code == 200
    data = res.json()
    assert data["supplier_id"] == "SUP-91013"
    assert data["client_risk_features"]["on_time_delivery_pct"] == 96.0


# -----------------------------------------------------------------------------
# Scenario 14: Unknown supplier mapping
# -----------------------------------------------------------------------------
def test_scenario_14_unknown_supplier_mapping(auth_client, fake_supplier_store):
    """Scenario 14: Unknown supplier code mapping strictly returns 404 without guessing or inventing IDs."""
    # Attempt to resolve an unknown client code
    canon_id = resolve_supplier_code_to_canonical_id("SUP-UNKNOWN-CODE")
    assert canon_id is None

    # Query endpoint
    res = auth_client.get("/api/v1/supplier-risk/client-suppliers/SUP-UNKNOWN-CODE/risk-score")
    assert res.status_code == 404
    data = res.json()
    assert data["error_code"] == "SUPPLIER_NOT_FOUND"


# -----------------------------------------------------------------------------
# Scenario 15: Invalid incident type
# -----------------------------------------------------------------------------
def test_scenario_15_invalid_incident_type():
    """Scenario 15: Invalid incident type raises ValueError and is safely rejected."""
    with pytest.raises(ValueError, match="Invalid incident type"):
        validate_incident_type("UnauthorizedType")

    incident = SupplierIncident(
        supplier_id="SUP-90001",
        incident_date="2026-10-01",
        incident_type="Bankruptcy",
    )
    assert incident.incident_type == "Other"


def test_saving_incidents_stores_unrecognised_types_as_other(fake_supplier_store):
    saved = save_supplier_incidents_data([
        {"supplier_id": "SUP-93006", "incident_date": "2026-09-01", "incident_type": "Compliance"},
        {"supplier_id": "SUP-93006", "incident_date": "2026-09-02", "incident_type": "packaging"},
        {"supplier_id": "SUP-93006", "incident_date": "2026-09-03", "incident_type": "delay"},
    ])

    assert saved == 3
    types = sorted(i["incident_type"] for i in fetch_client_incidents("SUP-93006"))
    assert types == ["Delay", "Other", "Other"]


def test_saving_an_incident_with_a_blank_type_is_rejected(fake_supplier_store):
    with pytest.raises(ValueError):
        save_supplier_incidents_data([
            {"supplier_id": "SUP-93007", "incident_date": "2026-09-01", "incident_type": "  "},
        ])


# -----------------------------------------------------------------------------
# Scenario 16: Invalid or missing incident date
# -----------------------------------------------------------------------------
def test_scenario_16_invalid_or_missing_incident_date():
    """Scenario 16: Invalid calendar date or missing date is safely rejected."""
    with pytest.raises(ValueError):
        validate_incident_date("2026-99-99")

    with pytest.raises(ValueError):
        validate_incident_date("not-a-date")

    with pytest.raises(ValueError):
        SupplierIncident(
            supplier_id="SUP-90001",
            incident_date="bad-date",
            incident_type="Delay",
        )


# -----------------------------------------------------------------------------
# Scenario 17: Missing optional fields
# -----------------------------------------------------------------------------
def test_scenario_17_missing_optional_fields():
    """Scenario 17: Optional fields (description, severity, resolved) handled safely."""
    inc = SupplierIncident(
        supplier_id="SUP-91017",
        incident_date="2026-10-01",
        incident_type="Delay",
        description=None,
        severity=None,
        resolved=None,
    )
    assert inc.description == ""
    assert inc.severity is None

    master = ClientSupplierMaster(
        supplier_id="SUP-91017",
        legal_name="Optional Co",
        country="India",
        city="Delhi",
        category="Hardware",
        on_time_delivery_pct=None,
    )
    assert master.on_time_delivery_pct is None


# -----------------------------------------------------------------------------
# Scenario 18: MongoDB / data-loading failure
# -----------------------------------------------------------------------------
def test_scenario_18_mongodb_data_loading_failure(auth_client, fake_supplier_store):
    """Scenario 18: Database errors propagate consistently to HTTP 503 RISK_UNAVAILABLE."""
    with patch("src.analyze.fetch_client_supplier", side_effect=PyMongoError("Simulated DB timeout")):
        res = auth_client.get("/api/v1/suppliers/SUP-90001/risk-score")
        assert res.status_code == 503
        assert res.json()["error_code"] == "RISK_UNAVAILABLE"


# -----------------------------------------------------------------------------
# Scenario 19: Cached assessment with new fields
# -----------------------------------------------------------------------------
def test_scenario_19_cached_assessment_with_new_fields(auth_client, fake_supplier_store):
    """Scenario 19: Cached document restores top_reasons and client_risk_features."""
    fake_supplier_store.suppliers.insert_one({
        "supplier_id": "SUP-91019",
        "name": "Cached New Fields Corp",
        "normalized_name": "cached new fields corp",
        "sanctions_flag": False,
    })
    cached_doc = {
        "supplier_id": "SUP-91019",
        "supplier_name": "Cached New Fields Corp",
        "score": 68.5,
        "tier": "Medium",
        "top_factors": [],
        "top_evidence_articles": [],
        "computed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "top_reasons": ["2 delay incidents in 12 months", "On-time delivery rate is 91.0%"],
        "client_risk_features": {
            "quality_incidents_12m": 0,
            "delay_incidents_12m": 2,
            "dispute_incidents_12m": 0,
            "other_incidents_12m": 0,
            "days_since_last_incident": 25,
            "on_time_delivery_pct": 91.0,
            "on_time_delivery_missing": False,
            "country": "India",
            "city": "Bengaluru",
            "category": "Logistics",
        },
    }
    fake_supplier_store.risk_assessments.insert_one(cached_doc)

    res = auth_client.get("/api/v1/suppliers/SUP-91019/risk-score")
    assert res.status_code == 200
    data = res.json()
    assert data["score"] == 68.5
    assert data["top_reasons"] == ["2 delay incidents in 12 months", "On-time delivery rate is 91.0%"]
    assert data["client_risk_features"]["delay_incidents_12m"] == 2


# -----------------------------------------------------------------------------
# Scenario 20: Old cached assessment without new fields
# -----------------------------------------------------------------------------
def test_scenario_20_old_cached_assessment_without_new_fields(auth_client, fake_supplier_store):
    """Scenario 20: Old cached assessment without new client fields deserializes safely without crashing."""
    fake_supplier_store.suppliers.insert_one({
        "supplier_id": "SUP-91020",
        "name": "Old Cache Corp",
        "normalized_name": "old cache corp",
        "sanctions_flag": False,
    })
    old_cached_doc = {
        "supplier_id": "SUP-91020",
        "supplier_name": "Old Cache Corp",
        "score": 55.0,
        "tier": "Low",
        "top_factors": [],
        "top_evidence_articles": [],
        "computed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    fake_supplier_store.risk_assessments.insert_one(old_cached_doc)

    res = auth_client.get("/api/v1/suppliers/SUP-91020/risk-score")
    assert res.status_code == 200
    data = res.json()
    assert data["score"] == 55.0
    assert data["tier"] == "Low"
    assert data["top_reasons"] == []
    assert data["client_risk_features"] is None


# -----------------------------------------------------------------------------
# Scenario 21: Existing API authentication tests
# -----------------------------------------------------------------------------
def test_scenario_21_existing_api_authentication(unauth_client):
    """Scenario 21: Missing credentials strictly return HTTP 401 UNAUTHORIZED."""
    res = unauth_client.get("/api/v1/suppliers/SUP-90001/risk-score")
    assert res.status_code == 401
    assert res.json()["error_code"] == "UNAUTHORIZED"


# -----------------------------------------------------------------------------
# Scenario 22: Existing endpoint aliases
# -----------------------------------------------------------------------------
def test_scenario_22_existing_endpoint_aliases(auth_client, fake_supplier_store):
    """Scenario 22: Gateway alias routes work consistently."""
    fake_supplier_store.suppliers.insert_one({
        "supplier_id": "SUP-91022",
        "name": "Alias Test Corp",
        "normalized_name": "alias test corp",
        "sanctions_flag": False,
    })
    res1 = auth_client.get("/api/v1/suppliers/SUP-91022/risk-score")
    res2 = auth_client.get("/api/v1/supplier-risk/SUP-91022/risk-score")
    res3 = auth_client.get("/api/v1/supplier-risk/suppliers/SUP-91022/risk-score")

    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res3.status_code == 200
    assert res1.json()["supplier_id"] == res2.json()["supplier_id"] == res3.json()["supplier_id"]


# -----------------------------------------------------------------------------
# Scenario 23: Existing no-evidence behavior
# -----------------------------------------------------------------------------
def test_scenario_23_existing_no_evidence_behavior(auth_client, fake_supplier_store):
    """Scenario 23: Known supplier with no headlines and no client data returns score: null, tier: null."""
    fake_supplier_store.suppliers.insert_one({
        "supplier_id": "SUP-91023",
        "name": "Quiet Supplier Corp",
        "normalized_name": "quiet supplier corp",
        "sanctions_flag": False,
    })
    res = auth_client.get("/api/v1/suppliers/SUP-91023/risk-score")
    assert res.status_code == 200
    data = res.json()
    assert data["score"] is None
    assert data["tier"] is None
    assert data["top_factors"] == []
    assert data["top_evidence_articles"] == []
    assert data["client_risk_features"] is None


# -----------------------------------------------------------------------------
# Scenario 24: Existing sanctions behavior
# -----------------------------------------------------------------------------
def test_scenario_24_existing_sanctions_behavior(auth_client, fake_supplier_store):
    """Scenario 24: Sanctioned supplier returns Critical risk tier and score >= 85.0."""
    res = auth_client.get("/api/v1/suppliers/SUP-90002/risk-score")
    assert res.status_code == 200
    data = res.json()
    assert data["score"] >= 85.0
    assert data["tier"] == "Critical"
    assert any(f["factor"] == "sanction" for f in data["top_factors"])
    assert any("Designated on" in r for r in data["top_reasons"])


# -----------------------------------------------------------------------------
# Scenario 25: Existing NLP scoring tests
# -----------------------------------------------------------------------------
def test_scenario_25_existing_nlp_scoring(auth_client, fake_supplier_store):
    """Scenario 25: Supplier with news headlines evaluates through NLP pipeline correctly."""
    headlines = {
        "NLP Test Corp": [
            {"headline": "NLP Test Corp announces major product recall.", "date": "2026-10-01", "score": 75.0}
        ]
    }
    fake_supplier_store.suppliers.insert_one({
        "supplier_id": "SUP-91025",
        "name": "NLP Test Corp",
        "normalized_name": "nlp test corp",
        "sanctions_flag": False,
    })
    with patch("src.analyze.load_active_trend_headlines", return_value=headlines):
        res = auth_client.get("/api/v1/suppliers/SUP-91025/risk-score")
        assert res.status_code == 200
        data = res.json()
        assert data["score"] is not None
        assert len(data["top_evidence_articles"]) > 0
        assert data["top_evidence_articles"][0]["headline"] == "NLP Test Corp announces major product recall."


# -----------------------------------------------------------------------------
# Configuration Validation Tests (Issue #350 Composite Risk Weights)
# -----------------------------------------------------------------------------
def test_composite_risk_weights_default_weights():
    """Default configuration provides balanced 0.5 client + 0.5 NLP risk weights summing to 1.0."""
    cfg = Settings()
    assert cfg.client_risk_weight == 0.5
    assert cfg.nlp_risk_weight == 0.5
    assert cfg.client_risk_weight + cfg.nlp_risk_weight == 1.0


def test_composite_risk_weights_valid_custom_weights(monkeypatch):
    """Valid custom weights 0.6 + 0.4 initialize cleanly via constructor and environment variables."""
    # 1. Constructor arguments
    cfg = Settings(client_risk_weight=0.6, nlp_risk_weight=0.4)
    assert cfg.client_risk_weight == 0.6
    assert cfg.nlp_risk_weight == 0.4
    assert round(cfg.client_risk_weight + cfg.nlp_risk_weight, 6) == 1.0

    # 2. Environment variables
    monkeypatch.setenv("CLIENT_RISK_WEIGHT", "0.6")
    monkeypatch.setenv("NLP_RISK_WEIGHT", "0.4")
    cfg_env = Settings()
    assert cfg_env.client_risk_weight == 0.6
    assert cfg_env.nlp_risk_weight == 0.4
    assert round(cfg_env.client_risk_weight + cfg_env.nlp_risk_weight, 6) == 1.0


def test_composite_risk_weights_negative_environment_weight_fails(monkeypatch):
    """Negative weight in environment variable or constructor must fail validation clearly."""
    # 1. Environment variable
    monkeypatch.setenv("CLIENT_RISK_WEIGHT", "-0.1")
    monkeypatch.setenv("NLP_RISK_WEIGHT", "1.1")
    with pytest.raises(ValueError, match="cannot be negative"):
        Settings()

    # 2. Explicit constructor
    with pytest.raises(ValueError, match="cannot be negative"):
        Settings(client_risk_weight=-0.2, nlp_risk_weight=1.2)


def test_composite_risk_weights_greater_than_one_environment_weight_fails(monkeypatch):
    """Weight greater than 1.0 in environment variable or constructor must fail validation clearly."""
    # 1. Environment variable
    monkeypatch.setenv("CLIENT_RISK_WEIGHT", "1.2")
    monkeypatch.setenv("NLP_RISK_WEIGHT", "-0.2")
    with pytest.raises(ValueError, match="(cannot exceed 1.0|cannot be negative)"):
        Settings()

    # 2. Explicit constructor
    with pytest.raises(ValueError, match="cannot exceed 1.0"):
        Settings(client_risk_weight=1.5, nlp_risk_weight=-0.5)


def test_composite_risk_weights_sum_not_one_fails(monkeypatch):
    """Weights whose sum does not equal 1.0 must fail validation with a clear message."""
    # 1. Environment variables summing to 1.1 != 1.0
    monkeypatch.setenv("CLIENT_RISK_WEIGHT", "0.7")
    monkeypatch.setenv("NLP_RISK_WEIGHT", "0.4")
    with pytest.raises(ValueError, match="must equal 1.0"):
        Settings()

    # 2. Environment variables summing to 0.8 != 1.0
    monkeypatch.setenv("CLIENT_RISK_WEIGHT", "0.3")
    monkeypatch.setenv("NLP_RISK_WEIGHT", "0.5")
    with pytest.raises(ValueError, match="must equal 1.0"):
        Settings()

    # 3. Explicit constructor arguments summing to 0.9 != 1.0
    with pytest.raises(ValueError, match="must equal 1.0"):
        Settings(client_risk_weight=0.5, nlp_risk_weight=0.4)


# -----------------------------------------------------------------------------
# Post-Review Verification Tests (Fixes 1, 2, 3)
# -----------------------------------------------------------------------------

def test_configurable_delivery_target_above_custom_target():
    """Fix 1: Custom delivery target 90%, actual 92% produces no below-target reason."""
    cfg = Settings(client_target_on_time_delivery_pct=90.0)
    features = ClientRiskFeatures(on_time_delivery_pct=92.0, on_time_delivery_missing=False)
    reasons = generate_top_reasons(features, config=cfg)
    assert not any("below" in r for r in reasons)
    assert any("92.0%" in r for r in reasons)


def test_configurable_delivery_target_below_custom_target():
    """Fix 1: Custom delivery target 90%, actual 88% produces below-90.0%-target reason."""
    cfg = Settings(client_target_on_time_delivery_pct=90.0)
    features = ClientRiskFeatures(on_time_delivery_pct=88.0, on_time_delivery_missing=False)
    reasons = generate_top_reasons(features, config=cfg)
    assert any("below 90.0% target" in r for r in reasons)


def test_incident_deduplication_two_same_day_distinct_retained(fake_supplier_store):
    """Fix 2: Two same-day Delay incidents with different descriptions are both retained."""
    supplier_rec = {
        "supplier_id": "SUP-91030",
        "name": "Distinct Same Day Corp",
        "normalized_name": "distinct same day corp",
        "sanctions_flag": False,
    }
    fake_supplier_store.suppliers.insert_one(supplier_rec)
    fake_supplier_store.client_suppliers.insert_one({
        "supplier_id": "SUP-91030",
        "supplier_code": "CL-30",
        "legal_name": "Distinct Same Day Corp",
        "country": "India",
        "city": "Hyderabad",
        "category": "Logistics",
    })
    # Two distinct Delay incidents on 2026-09-10 with missing incident_id
    fake_supplier_store.client_incidents.insert_one({
        "supplier_id": "SUP-91030",
        "incident_date": "2026-09-10",
        "incident_type": "Delay",
        "description": "Vessel arrival delayed at port",
        "severity": "medium",
    })
    fake_supplier_store.client_incidents.insert_one({
        "supplier_code": "CL-30",
        "incident_date": "2026-09-10",
        "incident_type": "Delay",
        "description": "Customs clearance delay at warehouse",
        "severity": "high",
    })

    res = compute_canonical_supplier_risk_score(supplier_rec, as_of_date="2026-10-15")
    assert res.client_risk_features is not None
    assert res.client_risk_features.delay_incidents_12m == 2


def test_incident_deduplication_identical_records_removed(fake_supplier_store):
    """Fix 2: Identical incident records under supplier_id and supplier_code have duplicate removed."""
    supplier_rec = {
        "supplier_id": "SUP-91031",
        "name": "Duplicate Incidents Ltd",
        "normalized_name": "duplicate incidents ltd",
        "sanctions_flag": False,
    }
    fake_supplier_store.suppliers.insert_one(supplier_rec)
    fake_supplier_store.client_suppliers.insert_one({
        "supplier_id": "SUP-91031",
        "supplier_code": "CL-31",
        "legal_name": "Duplicate Incidents Ltd",
        "country": "USA",
        "city": "Chicago",
        "category": "Freight",
    })
    # Identical incident record inserted under both supplier_id and supplier_code
    duplicate_incident_body = {
        "incident_date": "2026-09-10",
        "incident_type": "Delay",
        "description": "Port congestion hold",
        "severity": "medium",
    }
    fake_supplier_store.client_incidents.insert_one({
        "supplier_id": "SUP-91031",
        **duplicate_incident_body,
    })
    fake_supplier_store.client_incidents.insert_one({
        "supplier_code": "CL-31",
        **duplicate_incident_body,
    })

    res = compute_canonical_supplier_risk_score(supplier_rec, as_of_date="2026-10-15")
    assert res.client_risk_features is not None
    assert res.client_risk_features.delay_incidents_12m == 1


def test_etl_supplier_name_alias_populates_legal_name():
    """Fix 3: ETL supplier_name alias correctly populates legal_name."""
    m = ClientSupplierMaster(supplier_code="SUP-1001", supplier_name="Acme Tools Inc", city="Mumbai")
    assert m.legal_name == "Acme Tools Inc"
    assert m.supplier_code == "SUP-1001"


def test_etl_missing_country_and_category_handled_safely():
    """Fix 3: Missing country and category are handled safely without inventing business values."""
    m = ClientSupplierMaster(supplier_code="SUP-1002", supplier_name="Beta Logistics", city="Chennai")
    assert m.country is None
    assert m.category is None
    assert m.on_time_delivery_pct is None

    features = calculate_client_risk_features(m, [], scoring_date="2026-10-15")
    assert features.country is None
    assert features.category is None
    assert features.on_time_delivery_pct is None
    assert features.on_time_delivery_missing is True


def test_existing_issue_350_payload_preserves_all_explicit_values():
    """Fix 3: Existing Issue #350 payload preserves all explicitly supplied values intact."""
    payload = {
        "supplier_code": "SUP-2231",
        "legal_name": "Standard Parts GmbH",
        "country": "Germany",
        "city": "Munich",
        "category": "Machining",
        "on_time_delivery_pct": 97.4,
    }
    m = ClientSupplierMaster(**payload)
    assert m.supplier_code == "SUP-2231"
    assert m.legal_name == "Standard Parts GmbH"
    assert m.country == "Germany"
    assert m.city == "Munich"
    assert m.category == "Machining"
    assert m.on_time_delivery_pct == 97.4


def test_resolve_canonical_supplier_step5_propagates_pymongo_error():
    """Operational Fix 1: PyMongoError during Step 5 client_suppliers lookup is re-raised, not swallowed."""
    from src.supplier_mapping import resolve_canonical_supplier

    mock_map_col = MagicMock()
    mock_map_col.find_one.return_value = None  # Steps 1-4 return no match

    mock_client_col = MagicMock()
    mock_client_col.find_one.side_effect = PyMongoError("MongoDB connection lost during client lookup")

    with patch("src.db.get_client_suppliers_collection", return_value=mock_client_col):
        with pytest.raises(PyMongoError, match="MongoDB connection lost during client lookup"):
            resolve_canonical_supplier("UNMAPPED-CODE-001", collection=mock_map_col)


def test_client_supplier_endpoint_returns_503_on_database_outage(auth_client):
    """Operational Fix 1: MongoDB outage during client code resolution returns HTTP 503 RISK_UNAVAILABLE."""
    with patch("src.analyze.resolve_supplier_code_to_canonical_id", side_effect=PyMongoError("DB outage")):
        res = auth_client.get("/api/v1/supplier-risk/client-suppliers/SUP-2231/risk-score")
        assert res.status_code == 503
        data = res.json()
        assert data["error_code"] == "RISK_UNAVAILABLE"


def test_ensure_client_data_indexes_creates_all_indexes():
    """Operational Fix 2: ensure_client_data_indexes creates all indexes including idx_incident_code_date."""
    from src.db import ensure_client_data_indexes

    mock_scol = MagicMock()
    mock_scol.create_index.side_effect = lambda keys, name, **kwargs: name

    mock_icol = MagicMock()
    mock_icol.create_index.side_effect = lambda keys, name, **kwargs: name

    result = ensure_client_data_indexes(suppliers_col=mock_scol, incidents_col=mock_icol)

    assert result["suppliers"] == ["idx_client_supplier_id", "idx_client_supplier_code"]
    assert result["incidents"] == [
        "idx_incident_supplier_id",
        "idx_incident_supplier_code",
        "idx_incident_date",
        "idx_incident_supplier_date",
        "idx_incident_code_date",
    ]


def test_ensure_client_data_indexes_once_avoids_repeated_work():
    """Operational Fix 2: ensure_client_data_indexes_once executes once per process lifetime."""
    import src.db as db_module

    with patch("src.db.ensure_client_data_indexes") as mock_ensure:
        mock_ensure.return_value = {"suppliers": ["idx_s"], "incidents": ["idx_i"]}
        db_module._client_indexes_ensured = False

        res1 = db_module.ensure_client_data_indexes_once()
        assert res1 == {"suppliers": ["idx_s"], "incidents": ["idx_i"]}
        assert mock_ensure.call_count == 1

        # Second call should skip repeated work
        res2 = db_module.ensure_client_data_indexes_once()
        assert res2 == {"suppliers": [], "incidents": []}
        assert mock_ensure.call_count == 1


# -----------------------------------------------------------------------------
# Must-fix 1: Normalize Unknown Client Incident Types
# -----------------------------------------------------------------------------
def test_unrecognised_incident_types_count_as_other():
    assert normalize_incident_type("Compliance") == "Other"
    assert normalize_incident_type("packaging") == "Other"
    assert normalize_incident_type("delay") == "Delay"

    with pytest.raises(ValueError):
        normalize_incident_type("  ")


def test_every_valid_sample_incident_is_counted():
    with (
        CLIENT_SAMPLES / "supplier_incidents.csv"
    ).open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    valid_rows = []

    for row in rows:
        try:
            validate_incident_date(row["incident_date"])
        except ValueError:
            continue

        valid_rows.append(row)

    features = calculate_client_risk_features(
        master=None,
        incidents=rows,
        scoring_date="2026-11-16",
    )

    counted = (
        features.quality_incidents_12m
        + features.delay_incidents_12m
        + features.dispute_incidents_12m
        + features.other_incidents_12m
    )

    assert counted == len(valid_rows)
    assert features.other_incidents_12m > 0


# -----------------------------------------------------------------------------
# Must-fix 2: Prevent Historical Scores from Replacing Current Risk Assessment
# -----------------------------------------------------------------------------
def test_as_of_date_score_does_not_replace_the_current_score(
    auth_client,
    fake_supplier_store,
):
    fake_supplier_store.suppliers.insert_one({
        "supplier_id": "SUP-93001",
        "name": "As Of Probe Corp",
        "normalized_name": "as of probe corp",
        "sanctions_flag": False,
    })

    save_client_supplier({
        "supplier_id": "SUP-93001",
        "legal_name": "As Of Probe Corp",
        "on_time_delivery_pct": 99.0,
    })

    for incident_date in (
        "2026-10-01",
        "2026-10-05",
        "2026-10-09",
        "2026-10-12",
    ):
        save_client_incident({
            "supplier_id": "SUP-93001",
            "incident_date": incident_date,
            "incident_type": "Quality",
        })

    past = auth_client.get(
        "/api/v1/suppliers/SUP-93001/risk-score?as_of_date=2026-01-01"
    )

    current = auth_client.get(
        "/api/v1/suppliers/SUP-93001/risk-score"
    )

    assert past.status_code == 200
    assert current.status_code == 200

    assert (
        past.json()["client_risk_features"]["quality_incidents_12m"]
        == 0
    )

    assert (
        current.json()["client_risk_features"]["quality_incidents_12m"]
        == 4
    )

    assert current.json()["score"] > past.json()["score"]


# -----------------------------------------------------------------------------
# Must-fix 3: Make client_risk_features Nullable in OpenAPI Contract
# -----------------------------------------------------------------------------
def _risk_score_validator() -> Draft202012Validator:
    spec = yaml.safe_load(
        (
            REPO_ROOT
            / "contracts"
            / "openapi"
            / "supplier-risk.yaml"
        ).read_text(encoding="utf-8")
    )

    schema = {
        "$ref": "#/components/schemas/SupplierRiskScoreResponse",
        "components": spec["components"],
    }

    return Draft202012Validator(schema)


def test_response_without_client_data_matches_the_contract(
    auth_client,
    fake_supplier_store,
):
    fake_supplier_store.suppliers.insert_one({
        "supplier_id": "SUP-93002",
        "name": "Sanctioned Probe Corp",
        "normalized_name": "sanctioned probe corp",
        "sanctions_flag": True,
        "sanctions_list": "OFAC SDN",
    })

    res = auth_client.get(
        "/api/v1/suppliers/SUP-93002/risk-score"
    )

    assert res.status_code == 200
    assert res.json()["client_risk_features"] is None

    errors = list(
        _risk_score_validator().iter_errors(res.json())
    )

    assert errors == []


# -----------------------------------------------------------------------------
# Must-fix 4: Prevent Clean Client Data from Lowering NLP Risk Score
# -----------------------------------------------------------------------------
def test_clean_client_data_does_not_lower_the_news_score(
    fake_supplier_store,
    monkeypatch,
):
    fake_supplier_store.suppliers.insert_one({
        "supplier_id": "SUP-93003",
        "name": "News Risk Corp",
        "normalized_name": "news risk corp",
        "sanctions_flag": False,
    })

    save_client_supplier({
        "supplier_id": "SUP-93003",
        "legal_name": "News Risk Corp",
        "on_time_delivery_pct": 99.0,
    })

    monkeypatch.setattr(
        "src.analyze.load_active_trend_headlines",
        lambda: {
            "News Risk Corp": [
                {"headline": "News Risk Corp faces fraud probe"}
            ]
        },
    )

    monkeypatch.setattr(
        "src.analyze.calculate_supplier_trend",
        lambda *args, **kwargs: {
            "current_risk_score": 80.0,
            "current_risk_tier": "high",
            "top_evidence": [],
        },
    )

    res = compute_canonical_supplier_risk_score(
        {"supplier_id": "SUP-93003", "name": "News Risk Corp"},
        as_of_date="2026-11-16",
    )

    assert res.client_risk_features is not None
    assert res.score == 80.0
    assert res.tier == "high"


def test_weak_news_does_not_lower_a_higher_client_score(
    fake_supplier_store,
    monkeypatch,
):
    fake_supplier_store.suppliers.insert_one({
        "supplier_id": "SUP-93005",
        "name": "High Client Risk Corp",
        "normalized_name": "high client risk corp",
        "sanctions_flag": False,
    })

    save_client_supplier({
        "supplier_id": "SUP-93005",
        "legal_name": "High Client Risk Corp",
        "on_time_delivery_pct": 50.0,
    })

    monkeypatch.setattr(
        "src.analyze.load_active_trend_headlines",
        lambda: {
            "High Client Risk Corp": [
                {"headline": "Minor supply chain concern"}
            ]
        },
    )

    monkeypatch.setattr(
        "src.analyze.calculate_supplier_trend",
        lambda *args, **kwargs: {
            "current_risk_score": 20.0,
            "current_risk_tier": "Low",
            "top_evidence": [],
        },
    )

    res = compute_canonical_supplier_risk_score(
        {"supplier_id": "SUP-93005", "name": "High Client Risk Corp"},
        as_of_date="2026-11-16",
    )

    assert res.client_risk_features is not None
    # On-time 50% => delivery penalty 95 - 50 = 45.0, so the client score is 45.0.
    # The news score is 20.0. Weak news must not pull the client score down.
    assert res.score == 45.0
    assert res.tier == assign_risk_tier(45.0, get_settings())


# -----------------------------------------------------------------------------
# Regression: Client-only supplier IDs must remain unresolved
# -----------------------------------------------------------------------------
def test_client_supplier_id_not_in_seed_stays_unresolved(fake_supplier_store):
    from src.supplier_mapping import resolve_canonical_supplier

    fake_supplier_store.client_suppliers.insert_one(
        {"supplier_code": "ACME-1", "supplier_id": "SUP-99999"}
    )

    assert resolve_canonical_supplier("ACME-1") is None
