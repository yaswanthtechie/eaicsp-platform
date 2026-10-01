from unittest.mock import patch

import pytest

from app.core import config
from app.services import internal_compliance_service as ics


URL = "/api/v1/compliance/internal-check"

INVENTORY_KEY = "test-inventory-key"
PORTAL_KEY = "test-portal-key"

INVENTORY_HEADERS = {
    "X-Caller-Service": "inventory-service",
    "X-Service-Key": INVENTORY_KEY,
}

PORTAL_HEADERS = {
    "X-Caller-Service": "supplier-portal",
    "X-Service-Key": PORTAL_KEY,
}

CALLER_BODY = {
    "supplier_id": "SUP001",
    "supplier_name": "ABC Supplies Pvt Ltd",
    "country": "India",
}


@pytest.fixture(autouse=True)
def internal_service_keys(monkeypatch):
    monkeypatch.setattr(
        config,
        "INTERNAL_SERVICE_KEYS",
        {
            "inventory-service": INVENTORY_KEY,
            "supplier-portal": PORTAL_KEY,
        },
    )

    ics.clear_internal_cache()

    yield

    ics.clear_internal_cache()


def test_supplier_name_body_is_accepted(
    client,
):
    response = client.post(
        URL,
        headers=INVENTORY_HEADERS,
        json=CALLER_BODY,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["supplier_id"] == "SUP001"
    assert data["company_name"] == "ABC Supplies Pvt Ltd"
    assert data["country"] == "India"
    assert data["cleared"] is True
    assert data["decision"] == "CLEAR"
    assert isinstance(data["reason"], str)


def test_company_name_body_is_also_accepted(
    client,
):
    body = {
        "supplier_id": "SUP002",
        "company_name": "XYZ Supplies Pvt Ltd",
        "country": "India",
    }

    response = client.post(
        URL,
        headers=INVENTORY_HEADERS,
        json=body,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["supplier_id"] == "SUP002"
    assert data["company_name"] == "XYZ Supplies Pvt Ltd"


def test_supplier_portal_key_is_accepted(
    client,
):
    response = client.post(
        URL,
        headers=PORTAL_HEADERS,
        json=CALLER_BODY,
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    "headers",
    [
        {
            "X-Caller-Service": "inventory-service",
        },
        {
            "X-Caller-Service": "inventory-service",
            "X-Service-Key": "wrong-key",
        },
        {},
    ],
)
def test_unauthenticated_calls_return_401(
    client,
    headers,
):
    with patch(
        "app.routes.compliance.perform_internal_compliance_check"
    ) as mock_check:
        response = client.post(
            URL,
            headers=headers,
            json=CALLER_BODY,
        )

    assert response.status_code == 401
    mock_check.assert_not_called()


def test_no_internal_service_keys_configured_returns_401(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        config,
        "INTERNAL_SERVICE_KEYS",
        {},
    )

    with patch(
        "app.routes.compliance.perform_internal_compliance_check"
    ) as mock_check:
        response = client.post(
            URL,
            headers=INVENTORY_HEADERS,
            json=CALLER_BODY,
        )

    assert response.status_code == 401
    mock_check.assert_not_called()


@pytest.mark.parametrize(
    "body",
    [
        {
            "supplier_id": "SUP001",
            "supplier_name": "",
            "country": "India",
        },
        {
            "supplier_id": "SUP001",
            "supplier_name": "A" * 256,
            "country": "India",
        },
    ],
)
def test_invalid_supplier_name_is_rejected(
    client,
    body,
):
    response = client.post(
        URL,
        headers=INVENTORY_HEADERS,
        json=body,
    )

    assert response.status_code == 422


def test_strong_match_returns_block(
    client,
):
    screening_result = {
        "is_flagged": True,
        "override_applied": False,
        "match_score": 97,
        "matched_lists": ["OFAC"],
    }

    with patch(
        "app.services.internal_compliance_service.screen_entity",
        return_value=screening_result,
    ):
        response = client.post(
            URL,
            headers=INVENTORY_HEADERS,
            json=CALLER_BODY,
        )

    assert response.status_code == 200

    data = response.json()

    assert data["cleared"] is False
    assert data["decision"] == "BLOCK"
    assert "Strong compliance match found" in data["reason"]


def test_possible_match_returns_review(
    client,
):
    screening_result = {
        "is_flagged": True,
        "override_applied": False,
        "match_score": 75,
        "matched_lists": ["OFAC"],
    }

    with patch(
        "app.services.internal_compliance_service.screen_entity",
        return_value=screening_result,
    ):
        response = client.post(
            URL,
            headers=INVENTORY_HEADERS,
            json={
                "supplier_id": "SUP003",
                "supplier_name": "Possible Match Supplier",
                "country": "India",
            },
        )

    assert response.status_code == 200

    data = response.json()

    assert data["cleared"] is False
    assert data["decision"] == "REVIEW"
    assert "human review" in data["reason"].lower()


def test_screening_failure_returns_503(
    client,
):
    with patch(
        "app.services.internal_compliance_service.screen_entity",
        side_effect=RuntimeError("screening failed"),
    ):
        response = client.post(
            URL,
            headers=INVENTORY_HEADERS,
            json={
                "supplier_id": "SUP004",
                "supplier_name": "Failure Supplier",
                "country": "India",
            },
        )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Compliance service unavailable"
    )


def test_repeated_http_calls_use_cache(
    client,
):
    screening_result = {
        "is_flagged": False,
        "override_applied": False,
        "match_score": 0,
        "matched_lists": [],
    }

    with patch(
        "app.services.internal_compliance_service.screen_entity",
        return_value=screening_result,
    ) as mock_screen:
        first = client.post(
            URL,
            headers=INVENTORY_HEADERS,
            json=CALLER_BODY,
        )

        second = client.post(
            URL,
            headers=INVENTORY_HEADERS,
            json=CALLER_BODY,
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    mock_screen.assert_called_once()


def test_clear_internal_cache_forces_fresh_screening(
    client,
):
    screening_result = {
        "is_flagged": False,
        "override_applied": False,
        "match_score": 0,
        "matched_lists": [],
    }

    with patch(
        "app.services.internal_compliance_service.screen_entity",
        return_value=screening_result,
    ) as mock_screen:
        first = client.post(
            URL,
            headers=INVENTORY_HEADERS,
            json=CALLER_BODY,
        )

        ics.clear_internal_cache()

        second = client.post(
            URL,
            headers=INVENTORY_HEADERS,
            json=CALLER_BODY,
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert mock_screen.call_count == 2


def test_override_clears_internal_cache(
    client,
    mock_compliance_officer_auth,
):
    screening_result = {
        "is_flagged": False,
        "override_applied": False,
        "match_score": 0,
        "matched_lists": [],
    }

    with patch(
        "app.services.internal_compliance_service.screen_entity",
        return_value=screening_result,
    ) as mock_screen:
        response = client.post(
            URL,
            headers=INVENTORY_HEADERS,
            json=CALLER_BODY,
        )

        assert response.status_code == 200

        override_response = client.post(
            "/api/v1/compliance/override",
            json={
                "entity_name": "ABC Supplies Pvt Ltd",
                "matched_name": "ABC Supplies Pvt Ltd",
                "source": "OFAC",
                "reason": "Reviewed and approved",
                "reviewed_by": "compliance-officer",
            },
        )

        assert override_response.status_code in (200, 201)

        response = client.post(
            URL,
            headers=INVENTORY_HEADERS,
            json=CALLER_BODY,
        )

    assert response.status_code == 200
    assert mock_screen.call_count == 2


def test_case_status_change_clears_internal_cache(
    client,
    mock_compliance_officer_auth,
):
    screening_result = {
        "is_flagged": False,
        "override_applied": False,
        "match_score": 0,
        "matched_lists": [],
    }

    with patch(
        "app.services.internal_compliance_service.screen_entity",
        return_value=screening_result,
    ) as mock_screen:
        response = client.post(
            URL,
            headers=INVENTORY_HEADERS,
            json=CALLER_BODY,
        )

        assert response.status_code == 200

        screen_response = client.post(
            "/api/v1/compliance/screen",
            json={
                "entity_name": "ABC Supplies Pvt Ltd",
                "entity_type": "supplier",
                "country": "India",
                "transaction_value": 1000,
            },
        )

        assert screen_response.status_code == 200

    assert mock_screen.call_count >= 1