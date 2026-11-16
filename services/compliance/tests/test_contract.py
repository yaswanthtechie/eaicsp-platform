
from unittest.mock import patch

import pytest

from app.services import internal_compliance_service as ics


URL = "/api/v1/compliance/internal-check"

CALLER_BODY = {
    "supplier_id": "SUP-CONTRACT-001",
    "supplier_name": "Ambiguous Supplier",
    "country": "India",
}

HEADERS = {
    "X-API-Key": "contract-test-key",
}

RESPONSE_KEYS = {
    "supplier_id",
    "company_name",
    "country",
    "cleared",
    "decision",
    "reason",
}


@pytest.fixture(autouse=True)
def contract_service_auth(fake_platform):
    fake_platform(
        status_code=200,
        payload={
            "authenticated": True,
            "service": "inventory",
            "auth_type": "api_key",
        },
    )


@pytest.mark.parametrize(
    "screening_result, decision, cleared",
    [
        (
            {
                "is_flagged": False,
                "override_applied": False,
                "match_score": 0,
                "matched_lists": [],
            },
            "CLEAR",
            True,
        ),
        (
            {
                "is_flagged": True,
                "override_applied": False,
                "match_score": 85,
                "matched_lists": ["OFAC"],
            },
            "REVIEW",
            False,
        ),
        (
            {
                "is_flagged": True,
                "override_applied": False,
                "match_score": 97,
                "matched_lists": ["OFAC"],
            },
            "BLOCK",
            False,
        ),
    ],
)
def test_internal_check_contract(
    client, screening_result, decision, cleared,
):
    with patch.object(
        ics,
        "screen_entity",
        return_value=screening_result,
    ):
        response = client.post(
            URL,
            headers=HEADERS,
            json=CALLER_BODY,
        )

    assert response.status_code == 200

    data = response.json()

    assert set(data) == RESPONSE_KEYS
    assert data["supplier_id"] == "SUP-CONTRACT-001"
    assert data["company_name"] == "Ambiguous Supplier"
    assert data["country"] == "India"
    assert data["decision"] == decision
    assert data["cleared"] is cleared
    assert data["cleared"] == (data["decision"] == "CLEAR")
    assert isinstance(data["reason"], str) and data["reason"]


def test_internal_check_without_service_key_is_rejected(client):
    response = client.post(
        URL,
        headers={},
        json=CALLER_BODY,
    )

    assert response.status_code == 401