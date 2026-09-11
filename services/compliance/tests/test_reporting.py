from datetime import datetime, timedelta

from app.core.database import SessionLocal
from app.core.dependency import verify_token
from app.main import app
from app.models.audit import ComplianceAudit
from app.models.compliance_case import ComplianceCase
from app.services.reporting_service import get_compliance_summary


def _add_audit(db, entity_name, matched):
    audit = ComplianceAudit(
        entity_name=entity_name,
        matched=matched,
        matched_name=entity_name if matched else None,
        matched_lists="OFAC" if matched else "",
        match_score=100 if matched else 0,
        risk_score=80 if matched else 0,
        risk_factors="{}",
        country_risk_score=30,
        overall_supplier_risk=70 if matched else 20,
        screening_type="INITIAL",
        newly_flagged=False,
        service_name="compliance-service",
        duration_ms=10,
    )
    db.add(audit)


def _add_case(db, status, created_at, resolved_at=None):
    case = ComplianceCase(
        case_number=f"REPORT-{status}-{created_at.timestamp()}",
        entity_name=f"REPORT {status}",
        entity_type="supplier",
        country="India",
        matched_name="MATCH" if status != "OPEN" else None,
        matched_lists="OFAC" if status != "OPEN" else "",
        match_score=100 if status != "OPEN" else 0,
        risk_score=80 if status != "OPEN" else 0,
        screening_tier="MEDIUM",
        screening_action="ADDITIONAL_COMPLIANCE_REVIEW",
        status=status,
        created_at=created_at,
        resolved_at=resolved_at,
        resolution=status if status in {"CLEARED", "CONFIRMED"} else None,
    )
    db.add(case)


def test_compliance_summary_calculates_volume_flag_rate_and_open_cases():
    db = SessionLocal()

    try:
        _add_audit(db, "CLEAN COMPANY", False)
        _add_audit(db, "HAMAS", True)
        _add_audit(db, "ACME TRADING LTD", True)
        _add_case(db, "OPEN", datetime(2026, 9, 1, 10, 0, 0))
        _add_case(db, "UNDER_REVIEW", datetime(2026, 9, 1, 11, 0, 0))
        db.commit()

        summary = get_compliance_summary(db)

        assert summary["screening_volume"] == 3
        assert summary["flagged_count"] == 2
        assert summary["flag_rate"] == 66.67
        assert summary["open_cases"] == 2

    finally:
        db.close()


def test_compliance_summary_calculates_average_resolution_time():
    db = SessionLocal()

    try:
        created_one = datetime(2026, 9, 1, 10, 0, 0)
        resolved_one = created_one + timedelta(hours=10)
        created_two = datetime(2026, 9, 2, 10, 0, 0)
        resolved_two = created_two + timedelta(hours=20)

        _add_case(db, "CLEARED", created_one, resolved_one)
        _add_case(db, "CONFIRMED", created_two, resolved_two)
        db.commit()

        summary = get_compliance_summary(db)

        assert summary["average_resolution_time_hours"] == 15.0

    finally:
        db.close()


def test_compliance_summary_returns_zero_values_when_database_is_empty():
    db = SessionLocal()

    try:
        summary = get_compliance_summary(db)

        assert summary == {
            "screening_volume": 0,
            "flagged_count": 0,
            "flag_rate": 0.0,
            "open_cases": 0,
            "average_resolution_time_hours": 0.0,
        }

    finally:
        db.close()


def test_compliance_summary_api_requires_compliance_officer(
    client,
    mock_compliance_officer_auth,
):
    response = client.get(
        "/api/v1/compliance/reports/compliance-summary"
    )

    assert response.status_code == 200
    data = response.json()
    assert "screening_volume" in data
    assert "flag_rate" in data
    assert "open_cases" in data
    assert "average_resolution_time_hours" in data


def test_compliance_summary_api_rejects_missing_token(client):
    response = client.get(
        "/api/v1/compliance/reports/compliance-summary"
    )

    assert response.status_code == 401


def test_compliance_summary_api_rejects_wrong_role(client):
    async def mock_verify_token():
        return {
            "valid": True,
            "role": "procurement_manager",
            "user_id": 2,
            "email": "manager@example.com",
        }

    app.dependency_overrides[verify_token] = mock_verify_token

    try:
        response = client.get(
            "/api/v1/compliance/reports/compliance-summary"
        )
    finally:
        app.dependency_overrides.pop(verify_token, None)

    assert response.status_code == 403
