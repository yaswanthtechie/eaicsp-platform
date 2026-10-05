from unittest.mock import patch


def test_internal_check_api_contract(client):
    payload = {
        "supplier_id": "SUP-CONTRACT-001",
        "company_name": "Ambiguous Supplier",
        "country": "India",
    }

    with patch(
        "app.services.internal_compliance_service.screen_entity"
    ) as mock_screen:

        mock_screen.return_value = {
            "is_flagged": True,
            "override_applied": False,
            "match_score": 85,
            "matched_lists": ["OFAC"],
        }

        response = client.post(
            "/api/v1/compliance/internal-check",
            headers={
                "X-Caller-Service": "supplier-portal",
            },
            json=payload,
        )

    assert response.status_code == 200

    data = response.json()

    assert data["supplier_id"] == "SUP-CONTRACT-001"
    assert data["company_name"] == "Ambiguous Supplier"
    assert data["country"] == "India"

    assert data["cleared"] is False
    assert data["decision"] == "REVIEW"
    assert data["reason"]

    assert set(data.keys()) == {
        "supplier_id",
        "company_name",
        "country",
        "cleared",
        "decision",
        "reason",
    }