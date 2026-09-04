import httpx
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from app.main import app


client = TestClient(app)




def test_screen_api_clean_entity():
    response = client.post(
        "/api/v1/compliance/screen",
        json={
            "entity_name": "XYZ UNIQUE COMPANY 123",
            "entity_type": "supplier",
            "country": "India",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["entity_name"] == "XYZ UNIQUE COMPANY 123"
    assert data["entity_type"] == "supplier"
    assert data["country"] == "India"
    assert data["is_flagged"] is False
    assert data["matched_count"] == 0
    assert data["matched_name"] is None
    assert data["source"] == []
    assert data["override_applied"] is False


def test_screen_api_sanctioned_entity():
    response = client.post(
        "/api/v1/compliance/screen",
        json={
            "entity_name": "HAMAS",
            "entity_type": "supplier",
            "country": "India",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["entity_name"] == "HAMAS"
    assert data["is_flagged"] is True
    assert data["matched_name"] == "HAMAS"
    assert data["match_score"] >= 90
    assert data["matched_count"] >= 1
    assert len(data["source"]) >= 1



def test_screen_api_invalid_entity_type():
    response = client.post(
        "/api/v1/compliance/screen",
        json={
            "entity_name": "OpenAI",
            "entity_type": "invalid",
            "country": "India",
        },
    )

    assert response.status_code == 422

    data = response.json()

    assert data["detail"][0]["loc"][-1] == "entity_type"


def test_screen_api_empty_entity_name():
    response = client.post(
        "/api/v1/compliance/screen",
        json={
            "entity_name": "",
            "entity_type": "supplier",
            "country": "India",
        },
    )

    assert response.status_code == 422

    data = response.json()

    assert data["detail"][0]["loc"][-1] == "entity_name"


def test_screen_api_blank_entity_name():
    response = client.post(
        "/api/v1/compliance/screen",
        json={
            "entity_name": "     ",
            "entity_type": "supplier",
            "country": "India",
        },
    )

    assert response.status_code == 422

    data = response.json()

    assert data["detail"][0]["loc"][-1] == "entity_name"


def test_screen_api_missing_entity_name():
    response = client.post(
        "/api/v1/compliance/screen",
        json={
            "entity_type": "supplier",
            "country": "India",
        },
    )

    assert response.status_code == 422


def test_screen_api_missing_entity_type():
    response = client.post(
        "/api/v1/compliance/screen",
        json={
            "entity_name": "OpenAI",
            "country": "India",
        },
    )

    assert response.status_code == 422


def test_bulk_screen_api():
    response = client.post(
        "/api/v1/compliance/screen-bulk",
        json={
            "entity_names": [
                "HAMAS",
                "ABC Technologies",
                "OpenAI",
                "Microsoft",
            ],
            "entity_type": "supplier",
            "country": "India",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["entity_type"] == "supplier"
    assert data["country"] == "India"
    assert data["count"] == 4

    assert len(data["results"]) == 4

    assert data["results"][0]["entity_name"] == "HAMAS"
    assert data["results"][0]["is_flagged"] is True


def test_bulk_screen_api_empty_list():
    response = client.post(
        "/api/v1/compliance/screen-bulk",
        json={
            "entity_names": [],
            "entity_type": "supplier",
            "country": "India",
        },
    )

    assert response.status_code == 422

    data = response.json()

    assert data["detail"][0]["loc"][-1] == "entity_names"


def test_bulk_screen_api_invalid_entity_type():
    response = client.post(
        "/api/v1/compliance/screen-bulk",
        json={
            "entity_names": ["HAMAS", "OpenAI"],
            "entity_type": "invalid",
            "country": "India",
        },
    )

    assert response.status_code == 422

    data = response.json()

    assert data["detail"][0]["loc"][-1] == "entity_type"




def test_audit_history_api():
    response = client.get(
        "/api/v1/compliance/audit",
        params={"entity_name": "HAMAS"},
    )

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)


def test_audit_summary_api(mock_compliance_officer_auth):
    response = client.get(
        "/api/v1/compliance/audit/summary"
    )

    assert response.status_code == 200

    data = response.json()

    assert "total_screenings" in data
    assert "total_flagged" in data
    assert "overall_flag_rate" in data
    assert "flag_rate_over_time" in data
    assert "most_frequently_flagged_entities" in data

    assert isinstance(data["total_screenings"], int)
    assert isinstance(data["total_flagged"], int)
    assert isinstance(data["overall_flag_rate"], (int, float))
    assert isinstance(data["flag_rate_over_time"], list)
    assert isinstance(
        data["most_frequently_flagged_entities"],
        list,
    )

def test_bulk_screen_api_rejects_more_than_500_entities():
    payload = {
        "entity_names": [f"Entity {i}" for i in range(501)],
        "entity_type": "supplier",
        "country": "India",
    }

    response = client.post(
    "/api/v1/compliance/screen-bulk",
    json=payload,
)

    assert response.status_code == 422



def test_create_override_api(mock_compliance_officer_auth):
    response = client.post(
        "/api/v1/compliance/override",
        json={
            "entity_name": "TEST COMPANY",
            "matched_name": "TEST SANCTIONED COMPANY",
            "source": "OFAC",
            "reason": "API test false positive",
            "reviewed_by": "pytest",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["entity_name"] == "TEST COMPANY"
    assert data["matched_name"] == "TEST SANCTIONED COMPANY"
    assert data["source"] == "OFAC"
    assert data["reason"] == "API test false positive"
    assert data["reviewed_by"] == "pytest"
    assert "id" in data
    assert "created_at" in data


def test_create_override_api_missing_reason(mock_compliance_officer_auth):
    response = client.post(
        "/api/v1/compliance/override",
        json={
            "entity_name": "TEST COMPANY",
            "matched_name": "TEST SANCTIONED COMPANY",
            "source": "OFAC",
            "reviewed_by": "pytest",
        },
    )

    assert response.status_code == 422


def test_create_override_api_blank_entity_name(mock_compliance_officer_auth):
    response = client.post(
        "/api/v1/compliance/override",
        json={
            "entity_name": "     ",
            "matched_name": "TEST SANCTIONED COMPANY",
            "source": "OFAC",
            "reason": "Test reason",
            "reviewed_by": "pytest",
        },
    )

    assert response.status_code == 422




def test_read_override_api(mock_compliance_officer_auth):
    
    create_response = client.post(
        "/api/v1/compliance/override",
        json={
            "entity_name": "READ TEST COMPANY",
            "matched_name": "READ TEST MATCH",
            "source": "OFAC",
            "reason": "Testing read override",
            "reviewed_by": "pytest",
        },
    )

    assert create_response.status_code == 200

    response = client.get(
        "/api/v1/compliance/override",
        params={
            "entity_name": "READ TEST COMPANY",
            "matched_name": "READ TEST MATCH",
            "source": "OFAC",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["entity_name"] == "READ TEST COMPANY"
    assert data["matched_name"] == "READ TEST MATCH"
    assert data["source"] == "OFAC"




def test_read_all_overrides_api(mock_compliance_officer_auth):
    response = client.get(
        "/api/v1/compliance/overrides"
    )

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)



def test_remove_override_api(mock_compliance_officer_auth):
    
    create_response = client.post(
        "/api/v1/compliance/override",
        json={
            "entity_name": "DELETE TEST COMPANY",
            "matched_name": "DELETE TEST MATCH",
            "source": "OFAC",
            "reason": "Testing delete override",
            "reviewed_by": "pytest",
        },
    )

    assert create_response.status_code == 200

    
    response = client.delete(
        "/api/v1/compliance/override",
        params={
            "entity_name": "DELETE TEST COMPANY",
            "matched_name": "DELETE TEST MATCH",
            "source": "OFAC",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["message"] == "Override removed"
    assert data["entity_name"] == "DELETE TEST COMPANY"
    assert data["matched_name"] == "DELETE TEST MATCH"
    assert data["source"] == "OFAC"


def test_remove_nonexistent_override_api(mock_compliance_officer_auth):
    response = client.delete(
        "/api/v1/compliance/override",
        params={
            "entity_name": "DOES NOT EXIST",
            "matched_name": "NO MATCH",
            "source": "OFAC",
        },
    )

    assert response.status_code in (404, 200)




def test_override_affects_screening_api(mock_compliance_officer_auth):
    
    create_response = client.post(
        "/api/v1/compliance/override",
        json={
            "entity_name": "HAMAS",
            "matched_name": "HAMAS",
            "source": "OFAC",
            "reason": "Test false positive",
            "reviewed_by": "pytest",
        },
    )

    assert create_response.status_code == 200

   
    screen_response = client.post(
        "/api/v1/compliance/screen",
        json={
            "entity_name": "HAMAS",
            "entity_type": "supplier",
            "country": "India",
        },
    )

    assert screen_response.status_code == 200

    data = screen_response.json()

    
    assert data["matched_name"] == "HAMAS"
    assert data["match_score"] == 100

    
    assert data["is_flagged"] is False
    assert data["override_applied"] is True
    assert data["override_reason"] == "Test false positive"
    assert data["reviewed_by"] == "pytest"


    delete_response = client.delete(
        "/api/v1/compliance/override",
        params={
            "entity_name": "HAMAS",
            "matched_name": "HAMAS",
            "source": "OFAC",
        },
    )

    assert delete_response.status_code == 200


def test_removed_override_no_longer_applies():
    
    client.delete(
        "/api/v1/compliance/override",
        params={
            "entity_name": "HAMAS",
            "matched_name": "HAMAS",
            "source": "OFAC",
        },
    )

    response = client.post(
        "/api/v1/compliance/screen",
        json={
            "entity_name": "HAMAS",
            "entity_type": "supplier",
            "country": "India",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["is_flagged"] is True
    assert data["override_applied"] is False
    assert data["override_reason"] is None
    assert data["reviewed_by"] is None

