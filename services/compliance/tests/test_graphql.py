from datetime import datetime, timedelta

from app.core.database import SessionLocal
from app.models.audit import ComplianceAudit
from app.models.compliance_case import ComplianceCase


def _authorization_header():
    return {
        "Authorization": "Bearer valid-token",
    }


def _wrong_role_response():
    return {
        "valid": True,
        "user_id": 2,
        "email": "user@company.com",
        "role": "procurement_manager",
        "is_active": True,
    }


def _compliance_officer_response():
    return {
        "valid": True,
        "user_id": 1,
        "email": "compliance@company.com",
        "role": "compliance_officer",
        "is_active": True,
    }


def _seed_graphql_data():
    db = SessionLocal()

    try:
        now = datetime.utcnow()

        screening = ComplianceAudit(
            entity_name="GraphQL Test Supplier",
            country="India",
            matched=False,
            matched_name=None,
            matched_lists=None,
            match_score=0,
            risk_score=10.0,
            screening_type="INITIAL",
            newly_flagged=False,
            screening_run_id="graphql-test-run",
            service_name="test",
            duration_ms=10.0,
            created_at=now,
        )

        case = ComplianceCase(
            case_number="CASE-GRAPHQL-001",
            entity_name="GraphQL Test Supplier",
            normalized_entity_name="graphql test supplier",
            entity_type="supplier",
            country="India",
            matched_name="GRAPHQL TEST SUPPLIER",
            matched_lists="OFAC",
            match_score=95,
            risk_score=80.0,
            screening_tier="HIGH",
            screening_action="REVIEW",
            status="OPEN",
            created_at=now,
            updated_at=now,
        )

        db.add(screening)
        db.add(case)
        db.commit()

    finally:
        db.close()


def test_graphql_without_token_returns_401(client):
    response = client.post(
        "/api/v1/compliance/graphql",
        json={
            "query": """
                {
                    screenings(limit: 5) {
                        total
                    }
                }
            """
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Missing authentication token"
    )


def test_graphql_wrong_role_returns_403(
    client,
    fake_platform,
):
    fake_platform(
        status_code=200,
        payload=_wrong_role_response(),
    )

    response = client.post(
        "/api/v1/compliance/graphql",
        headers=_authorization_header(),
        json={
            "query": """
                {
                    screenings(limit: 5) {
                        total
                    }
                }
            """
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Role 'procurement_manager' "
        "is not authorized for this endpoint"
    )


def test_graphql_compliance_officer_can_query_screenings(
    client,
    fake_platform,
):
    fake_platform(
        status_code=200,
        payload=_compliance_officer_response(),
    )

    _seed_graphql_data()

    response = client.post(
        "/api/v1/compliance/graphql",
        headers=_authorization_header(),
        json={
            "query": """
                {
                    screenings(limit: 5) {
                        total
                        items {
                            id
                            entityName
                            country
                            status
                            matched
                        }
                    }
                }
            """
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert "errors" not in body
    assert body["data"]["screenings"]["total"] >= 1

    item = next(
        item
        for item in body["data"]["screenings"]["items"]
        if item["entityName"] == "GraphQL Test Supplier"
    )

    assert item["country"] == "India"
    assert item["status"] == "CLEAR"
    assert item["matched"] is False


def test_graphql_compliance_officer_can_query_cases(
    client,
    fake_platform,
):
    fake_platform(
        status_code=200,
        payload=_compliance_officer_response(),
    )

    _seed_graphql_data()

    response = client.post(
        "/api/v1/compliance/graphql",
        headers=_authorization_header(),
        json={
            "query": """
                {
                    cases(limit: 5) {
                        total
                        items {
                            id
                            caseNumber
                            entityName
                            country
                            status
                        }
                    }
                }
            """
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert "errors" not in body
    assert body["data"]["cases"]["total"] >= 1

    item = next(
        item
        for item in body["data"]["cases"]["items"]
        if item["caseNumber"] == "CASE-GRAPHQL-001"
    )

    assert item["entityName"] == "GraphQL Test Supplier"
    assert item["country"] == "India"
    assert item["status"] == "OPEN"


def test_graphql_screening_filters_and_pagination(
    client,
    fake_platform,
):
    fake_platform(
        status_code=200,
        payload=_compliance_officer_response(),
    )

    db = SessionLocal()

    try:
        now = datetime.utcnow()

        first = ComplianceAudit(
            entity_name="India Clear Supplier",
            country="India",
            matched=False,
            matched_name=None,
            matched_lists=None,
            match_score=0,
            risk_score=10.0,
            screening_type="INITIAL",
            newly_flagged=False,
            duration_ms=5.0,
            created_at=now,
        )

        second = ComplianceAudit(
            entity_name="US Blocked Supplier",
            country="USA",
            matched=True,
            matched_name="US BLOCKED SUPPLIER",
            matched_lists="OFAC",
            match_score=95,
            risk_score=90.0,
            screening_type="INITIAL",
            newly_flagged=True,
            duration_ms=5.0,
            created_at=now - timedelta(minutes=1),
        )

        db.add_all([first, second])
        db.commit()

    finally:
        db.close()

    response = client.post(
        "/api/v1/compliance/graphql",
        headers=_authorization_header(),
        json={
            "query": """
                {
                    screenings(
                        status: CLEAR
                        jurisdiction: "India"
                        limit: 1
                        offset: 0
                    ) {
                        total
                        limit
                        offset
                        items {
                            entityName
                            country
                            status
                        }
                    }
                }
            """
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert "errors" not in body

    screenings = body["data"]["screenings"]

    assert screenings["total"] >= 1
    assert screenings["limit"] == 1
    assert screenings["offset"] == 0

    assert screenings["items"][0]["country"] == "India"
    assert screenings["items"][0]["status"] == "CLEAR"

def test_graphql_analyst_is_rejected(client, fake_platform):
    fake_platform(
        status_code=200,
        payload={
            "valid": True,
            "user_id": 3,
            "email": "analyst@company.com",
            "role": "analyst",
            "is_active": True,
        },
    )

    response = client.post(
        "/api/v1/compliance/graphql",
        headers=_authorization_header(),
        json={"query": "{ screenings(limit: 5) { total } }"},
    )

    assert response.status_code == 403


def test_graphql_review_filter_returns_review_screenings(client, fake_platform):
    db = SessionLocal()

    try:
        db.add(
            ComplianceAudit(
                entity_name="Review Supplier",
                country="India",
                matched=True,
                decision="REVIEW",
                matched_name="REVIEW SUPPLIER",
                matched_lists="OFAC",
                match_score=85,
                risk_score=60.0,
                screening_type="INITIAL",
                newly_flagged=False,
                service_name="test",
                duration_ms=1.0,
                created_at=datetime.utcnow(),
            )
        )
        db.commit()
    finally:
        db.close()

    fake_platform()

    response = client.post(
        "/api/v1/compliance/graphql",
        headers=_authorization_header(),
        json={
            "query": "{ screenings(status: REVIEW) "
                     "{ total items { entityName status } } }"
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert "errors" not in body
    assert body["data"]["screenings"]["total"] == 1
    assert body["data"]["screenings"]["items"][0]["status"] == "REVIEW"