from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import verify_token

from app.services.supplier_contract_service import (
    supplier_contracts,
    supplier_contract_history,
)

from app.services.supplier_onboarding_service import (
    suppliers,
    supplier_documents,
    supplier_onboarding_history,
)


client = TestClient(app)


# ============================================================
# TEST DATA
# ============================================================

SUP001 = "SUP001"
SUP002 = "SUP002"


PROCUREMENT_USER = {
    "user_id": 4,
    "role": "procurement_manager",
    "full_name": "Procurement Manager",
    "email": "procurement@example.com",
    "supplier_id": None,
}


SUPPLIER_1_USER = {
    "user_id": 8,
    "role": "supplier",
    "full_name": "Supplier One",
    "email": "supplier1@example.com",
    "supplier_id": SUP001,
}


SUPPLIER_2_USER = {
    "user_id": 99,
    "role": "supplier",
    "full_name": "Supplier Two",
    "email": "supplier2@example.com",
    "supplier_id": SUP002,
}


# ============================================================
# AUTHENTICATION HELPERS
# ============================================================

def authenticate_as(user):
    """
    Mock Platform Service authentication by overriding
    the real verify_token dependency.

    This is the same authentication isolation pattern
    used by the Supplier Portal API tests.
    """

    async def mock_verify_token():
        return user

    app.dependency_overrides[verify_token] = mock_verify_token


def clear_authentication():
    """
    Remove only the verify_token override.

    Do not clear every dependency override because other
    project-level test fixtures may use dependency overrides.
    """

    app.dependency_overrides.pop(verify_token, None)


# ============================================================
# SUPPLIER HELPERS
# ============================================================

def make_supplier_active(supplier_id: str):
    """
    Create an active supplier directly in the onboarding stores.

    Contract creation requires the supplier to already be active.
    """

    now = "2026-09-21T00:00:00+00:00"

    suppliers[supplier_id] = {
        "supplier_id": supplier_id,
        "company_name": f"{supplier_id} Company",
        "contact_name": f"{supplier_id} Contact",
        "email": f"{supplier_id.lower()}@example.com",
        "phone": "+919999999999",
        "address": "Hyderabad, Telangana",
        "required_documents": [
            "pan_card",
            "gst_certificate",
            "bank_certificate",
        ],
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }

    supplier_documents[supplier_id] = []
    supplier_onboarding_history[supplier_id] = []


def clear_contract_stores():
    supplier_contracts.clear()
    supplier_contract_history.clear()


# ============================================================
# PAYLOAD HELPERS
# ============================================================

def contract_payload(
    supplier_id=SUP001,
    contract_number="SC-2026-001",
    start_date="2026-10-01",
    end_date="2027-09-30",
):
    return {
        "supplier_id": supplier_id,
        "contract_number": contract_number,
        "title": "Laptop Supply Agreement",
        "description": "Annual laptop supply agreement",
        "start_date": start_date,
        "end_date": end_date,
        "payment_terms": "Net 30",
        "delivery_terms": "7 days",
        "pricing_terms": "Fixed",
        "minimum_order_value": 500000,
        "renewal_notice_days": 30,
        "auto_renew": False,
    }


# ============================================================
# FIXTURE
# ============================================================

@pytest.fixture(autouse=True)
def reset_contract_data():
    """
    Keep every contract test isolated.
    """

    clear_authentication()
    clear_contract_stores()

    suppliers.clear()
    supplier_documents.clear()
    supplier_onboarding_history.clear()

    make_supplier_active(SUP001)
    make_supplier_active(SUP002)

    yield

    clear_authentication()
    clear_contract_stores()

    suppliers.clear()
    supplier_documents.clear()
    supplier_onboarding_history.clear()


# ============================================================
# BASIC SERVICE TESTS
# ============================================================

def test_create_contract_success():
    authenticate_as(PROCUREMENT_USER)

    response = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["supplier_id"] == SUP001
    assert data["contract_number"] == "SC-2026-001"
    assert data["title"] == "Laptop Supply Agreement"
    assert data["status"] == "draft"
    assert data["expiring_soon"] is False
    assert data["days_until_expiry"] >= 0

    assert data["contract_id"].startswith("CNT-")
    assert data["created_by"] == str(PROCUREMENT_USER["user_id"])


def test_create_contract_requires_active_supplier():
    authenticate_as(PROCUREMENT_USER)

    suppliers["SUP-INACTIVE"] = {
        "supplier_id": "SUP-INACTIVE",
        "company_name": "Inactive Supplier",
        "status": "pending_documents",
    }

    response = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(
            supplier_id="SUP-INACTIVE",
            contract_number="SC-INACTIVE-001",
        ),
    )

    assert response.status_code == 400
    assert "active" in response.json()["detail"].lower()


def test_create_contract_unknown_supplier_returns_404():
    authenticate_as(PROCUREMENT_USER)

    response = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(
            supplier_id="SUP-UNKNOWN",
            contract_number="SC-UNKNOWN-001",
        ),
    )

    assert response.status_code == 404


def test_create_contract_duplicate_contract_number():
    authenticate_as(PROCUREMENT_USER)

    first = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(),
    )

    assert first.status_code == 201

    second = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(),
    )

    assert second.status_code in (400, 409)
    assert "already" in second.json()["detail"].lower()


def test_create_contract_duplicate_number_is_case_insensitive():
    authenticate_as(PROCUREMENT_USER)

    first = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(
            contract_number="SC-CASE-001",
        ),
    )

    assert first.status_code == 201

    second = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(
            contract_number="sc-case-001",
        ),
    )

    assert second.status_code in (400, 409)


# ============================================================
# VALIDATION TESTS
# ============================================================

def test_create_contract_end_date_must_be_after_start_date():
    authenticate_as(PROCUREMENT_USER)

    response = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(
            start_date="2027-01-01",
            end_date="2026-01-01",
        ),
    )

    assert response.status_code in (400, 422)


def test_create_contract_rejects_invalid_supplier_id():
    authenticate_as(PROCUREMENT_USER)

    payload = contract_payload()
    payload["supplier_id"] = "SUP 001"

    response = client.post(
        "/api/v1/supplier-contracts",
        json=payload,
    )

    assert response.status_code == 422


def test_create_contract_requires_contract_number():
    authenticate_as(PROCUREMENT_USER)

    payload = contract_payload()
    payload.pop("contract_number")

    response = client.post(
        "/api/v1/supplier-contracts",
        json=payload,
    )

    assert response.status_code == 422


def test_create_contract_requires_title():
    authenticate_as(PROCUREMENT_USER)

    payload = contract_payload()
    payload.pop("title")

    response = client.post(
        "/api/v1/supplier-contracts",
        json=payload,
    )

    assert response.status_code == 422


def test_create_contract_rejects_negative_minimum_order_value():
    authenticate_as(PROCUREMENT_USER)

    payload = contract_payload()
    payload["minimum_order_value"] = -1

    response = client.post(
        "/api/v1/supplier-contracts",
        json=payload,
    )

    assert response.status_code == 422


def test_create_contract_rejects_invalid_renewal_notice_days():
    authenticate_as(PROCUREMENT_USER)

    payload = contract_payload()
    payload["renewal_notice_days"] = 0

    response = client.post(
        "/api/v1/supplier-contracts",
        json=payload,
    )

    assert response.status_code == 422


# ============================================================
# GET CONTRACT
# ============================================================

def create_contract():
    authenticate_as(PROCUREMENT_USER)

    response = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(),
    )

    assert response.status_code == 201

    return response.json()


def test_get_contract_success():
    created = create_contract()

    authenticate_as(PROCUREMENT_USER)

    response = client.get(
        f"/api/v1/supplier-contracts/{created['contract_id']}",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["contract_id"] == created["contract_id"]
    assert data["supplier_id"] == SUP001
    assert data["contract_number"] == "SC-2026-001"


def test_get_unknown_contract_returns_404():
    authenticate_as(PROCUREMENT_USER)

    response = client.get(
        "/api/v1/supplier-contracts/CNT-NOT-FOUND",
    )

    assert response.status_code == 404


# ============================================================
# LIST CONTRACTS
# ============================================================

def test_list_contracts_returns_contracts():
    create_contract()

    authenticate_as(PROCUREMENT_USER)

    response = client.get(
        "/api/v1/supplier-contracts",
    )

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["contract_number"] == "SC-2026-001"


def test_list_contracts_filter_by_supplier():
    authenticate_as(PROCUREMENT_USER)

    first = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(
            supplier_id=SUP001,
            contract_number="SC-SUP1-001",
        ),
    )

    second = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(
            supplier_id=SUP002,
            contract_number="SC-SUP2-001",
        ),
    )

    assert first.status_code == 201
    assert second.status_code == 201

    response = client.get(
        "/api/v1/supplier-contracts",
        params={"supplier_id": SUP001},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["supplier_id"] == SUP001


def test_list_contracts_filter_by_status():
    create_contract()

    authenticate_as(PROCUREMENT_USER)

    response = client.get(
        "/api/v1/supplier-contracts",
        params={"status": "draft"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "draft"


def test_list_contracts_invalid_status():
    authenticate_as(PROCUREMENT_USER)

    response = client.get(
        "/api/v1/supplier-contracts",
        params={"status": "invalid-status"},
    )

    assert response.status_code == 422


# ============================================================
# SUPPLIER SCOPING
# ============================================================

def test_supplier_can_view_own_contract():
    created = create_contract()

    authenticate_as(SUPPLIER_1_USER)

    response = client.get(
        f"/api/v1/supplier-contracts/{created['contract_id']}",
    )

    assert response.status_code == 200
    assert response.json()["supplier_id"] == SUP001


def test_supplier_cannot_view_other_supplier_contract():
    authenticate_as(PROCUREMENT_USER)

    created = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(
            supplier_id=SUP002,
            contract_number="SC-SUP2-001",
        ),
    )

    assert created.status_code == 201

    contract_id = created.json()["contract_id"]

    authenticate_as(SUPPLIER_1_USER)

    response = client.get(
        f"/api/v1/supplier-contracts/{contract_id}",
    )

    assert response.status_code == 403


def test_supplier_list_is_scoped_to_own_supplier():
    authenticate_as(PROCUREMENT_USER)

    first = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(
            supplier_id=SUP001,
            contract_number="SC-SUP1-001",
        ),
    )

    second = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(
            supplier_id=SUP002,
            contract_number="SC-SUP2-001",
        ),
    )

    assert first.status_code == 201
    assert second.status_code == 201

    authenticate_as(SUPPLIER_1_USER)

    response = client.get(
        "/api/v1/supplier-contracts",
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["supplier_id"] == SUP001


def test_supplier_cannot_override_supplier_scope():
    authenticate_as(PROCUREMENT_USER)

    response = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(
            supplier_id=SUP002,
            contract_number="SC-SUP2-001",
        ),
    )

    assert response.status_code == 201

    authenticate_as(SUPPLIER_1_USER)

    response = client.get(
        "/api/v1/supplier-contracts",
        params={"supplier_id": SUP002},
    )

    assert response.status_code == 403


# ============================================================
# UPDATE CONTRACT
# ============================================================

def test_update_contract_success():
    created = create_contract()

    authenticate_as(PROCUREMENT_USER)

    response = client.put(
        f"/api/v1/supplier-contracts/{created['contract_id']}",
        json={
            "title": "Updated Laptop Supply Agreement",
            "payment_terms": "Net 45",
            "delivery_terms": "10 days",
            "minimum_order_value": 600000,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["title"] == "Updated Laptop Supply Agreement"
    assert data["payment_terms"] == "Net 45"
    assert data["delivery_terms"] == "10 days"
    assert data["minimum_order_value"] == 600000


def test_update_unknown_contract_returns_404():
    authenticate_as(PROCUREMENT_USER)

    response = client.put(
        "/api/v1/supplier-contracts/CNT-NOT-FOUND",
        json={
            "title": "Updated Contract",
        },
    )

    assert response.status_code == 404


def test_update_contract_invalid_end_date():
    created = create_contract()

    authenticate_as(PROCUREMENT_USER)

    response = client.put(
        f"/api/v1/supplier-contracts/{created['contract_id']}",
        json={
            "end_date": "2026-01-01",
        },
    )

    assert response.status_code in (400, 422)


# ============================================================
# CONTRACT ACTIVATION
# ============================================================

def test_activate_contract_success():
    created = create_contract()

    authenticate_as(PROCUREMENT_USER)

    response = client.post(
        f"/api/v1/supplier-contracts/{created['contract_id']}/activate",
    )

    assert response.status_code in (200, 201)

    data = response.json()

    assert data["status"] == "active"


def test_activate_contract_twice_is_rejected():
    created = create_contract()

    authenticate_as(PROCUREMENT_USER)

    first = client.post(
        f"/api/v1/supplier-contracts/{created['contract_id']}/activate",
    )

    assert first.status_code in (200, 201)

    second = client.post(
        f"/api/v1/supplier-contracts/{created['contract_id']}/activate",
    )

    assert second.status_code == 400


def test_activate_unknown_contract():
    authenticate_as(PROCUREMENT_USER)

    response = client.post(
        "/api/v1/supplier-contracts/CNT-NOT-FOUND/activate",
    )

    assert response.status_code == 404


# ============================================================
# CONTRACT RENEWAL
# ============================================================

def test_renew_active_contract_success():
    created = create_contract()

    authenticate_as(PROCUREMENT_USER)

    activate_response = client.post(
        f"/api/v1/supplier-contracts/{created['contract_id']}/activate",
    )

    assert activate_response.status_code in (200, 201)

    response = client.post(
        f"/api/v1/supplier-contracts/{created['contract_id']}/renew",
        json={
            "new_start_date": "2027-10-01",
            "new_end_date": "2028-09-30",
            "reason": "Annual supplier agreement renewed",
        },
    )

    assert response.status_code in (200, 201)

    data = response.json()

    assert data["contract_id"] == created["contract_id"]
    assert data["supplier_id"] == SUP001
    assert data["status"] == "active"
    assert data["previous_end_date"] == "2027-09-30"
    assert data["new_start_date"] == "2027-10-01"
    assert data["new_end_date"] == "2028-09-30"
    assert data["reason"] == "Annual supplier agreement renewed"


def test_renew_contract_requires_valid_dates():
    created = create_contract()

    authenticate_as(PROCUREMENT_USER)

    activate_response = client.post(
        f"/api/v1/supplier-contracts/{created['contract_id']}/activate",
    )

    assert activate_response.status_code in (200, 201)

    response = client.post(
        f"/api/v1/supplier-contracts/{created['contract_id']}/renew",
        json={
            "new_start_date": "2027-01-01",
            "new_end_date": "2026-01-01",
            "reason": "Invalid renewal",
        },
    )

    assert response.status_code in (400, 422)


def test_renew_contract_cannot_have_end_before_start():
    created = create_contract()

    authenticate_as(PROCUREMENT_USER)

    activate_response = client.post(
        f"/api/v1/supplier-contracts/{created['contract_id']}/activate",
    )

    assert activate_response.status_code in (200, 201)

    response = client.post(
        f"/api/v1/supplier-contracts/{created['contract_id']}/renew",
        json={
            "new_start_date": "2027-10-01",
            "new_end_date": "2027-09-01",
        },
    )

    assert response.status_code in (400, 422)


def test_renew_contract_cannot_start_before_current_end_date():
    created = create_contract()

    authenticate_as(PROCUREMENT_USER)

    activate_response = client.post(
        f"/api/v1/supplier-contracts/{created['contract_id']}/activate",
    )

    assert activate_response.status_code in (200, 201)

    response = client.post(
        f"/api/v1/supplier-contracts/{created['contract_id']}/renew",
        json={
            "new_start_date": "2027-09-01",
            "new_end_date": "2028-09-01",
        },
    )

    assert response.status_code == 400


def test_renew_unknown_contract():
    authenticate_as(PROCUREMENT_USER)

    response = client.post(
        "/api/v1/supplier-contracts/CNT-NOT-FOUND/renew",
        json={
            "new_start_date": "2027-10-01",
            "new_end_date": "2028-09-30",
        },
    )

    assert response.status_code == 404


# ============================================================
# EXPIRY CALCULATION
# ============================================================

def test_contract_reports_days_until_expiry():
    authenticate_as(PROCUREMENT_USER)

    future_date = date.today() + timedelta(days=20)

    response = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(
            contract_number="SC-EXPIRY-001",
            end_date=future_date.isoformat(),
        ),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["days_until_expiry"] == 20
    assert data["expiring_soon"] is True


def test_contract_not_expiring_soon_when_outside_notice_window():
    authenticate_as(PROCUREMENT_USER)

    future_date = date.today() + timedelta(days=100)

    response = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(
            contract_number="SC-FUTURE-001",
            end_date=future_date.isoformat(),
        ),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["days_until_expiry"] == 100
    assert data["expiring_soon"] is False

def test_expired_contract_is_reported_as_expired():
    authenticate_as(PROCUREMENT_USER)

    past_end_date = date.today() - timedelta(days=1)
    past_start_date = past_end_date - timedelta(days=30)

    response = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(
            contract_number="SC-EXPIRED-001",
            start_date=past_start_date.isoformat(),
            end_date=past_end_date.isoformat(),
        ),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["contract_number"] == "SC-EXPIRED-001"
    assert data["start_date"] == past_start_date.isoformat()
    assert data["end_date"] == past_end_date.isoformat()
    assert data["status"] == "expired"
    assert data["expiring_soon"] is False
    assert data["days_until_expiry"] == -1
    
# ============================================================
# EXPIRING CONTRACTS
# ============================================================

def test_list_expiring_contracts():
    authenticate_as(PROCUREMENT_USER)

    expiry_date = date.today() + timedelta(days=15)

    response = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(
            contract_number="SC-EXPIRING-001",
            end_date=expiry_date.isoformat(),
        ),
    )

    assert response.status_code == 201

    response = client.get(
        "/api/v1/supplier-contracts/expiring",
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["contract_number"] == "SC-EXPIRING-001"
    assert data[0]["expiring_soon"] is True


def test_expiring_contracts_can_be_filtered_by_supplier():
    authenticate_as(PROCUREMENT_USER)

    expiry_date = date.today() + timedelta(days=15)

    first = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(
            supplier_id=SUP001,
            contract_number="SC-SUP1-EXPIRING",
            end_date=expiry_date.isoformat(),
        ),
    )

    second = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(
            supplier_id=SUP002,
            contract_number="SC-SUP2-EXPIRING",
            end_date=expiry_date.isoformat(),
        ),
    )

    assert first.status_code == 201
    assert second.status_code == 201

    response = client.get(
        "/api/v1/supplier-contracts/expiring",
        params={"supplier_id": SUP001},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["supplier_id"] == SUP001


def test_supplier_expiring_contracts_are_scoped():
    authenticate_as(PROCUREMENT_USER)

    expiry_date = date.today() + timedelta(days=15)

    first = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(
            supplier_id=SUP001,
            contract_number="SC-SUP1-EXPIRING",
            end_date=expiry_date.isoformat(),
        ),
    )

    second = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(
            supplier_id=SUP002,
            contract_number="SC-SUP2-EXPIRING",
            end_date=expiry_date.isoformat(),
        ),
    )

    assert first.status_code == 201
    assert second.status_code == 201

    authenticate_as(SUPPLIER_1_USER)

    response = client.get(
        "/api/v1/supplier-contracts/expiring",
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["supplier_id"] == SUP001


def test_supplier_cannot_request_other_supplier_expiring_contracts():
    authenticate_as(SUPPLIER_1_USER)

    response = client.get(
        "/api/v1/supplier-contracts/expiring",
        params={"supplier_id": SUP002},
    )

    assert response.status_code == 403


# ============================================================
# HISTORY
# ============================================================

def test_contract_history_created_on_creation():
    created = create_contract()

    authenticate_as(PROCUREMENT_USER)

    response = client.get(
        f"/api/v1/supplier-contracts/{created['contract_id']}/history",
    )

    assert response.status_code == 200

    history = response.json()

    assert len(history) >= 1

    first = history[0]

    assert first["contract_id"] == created["contract_id"]
    assert first["supplier_id"] == SUP001
    assert first["to_status"] == "draft"


def test_contract_history_contains_activation():
    created = create_contract()

    authenticate_as(PROCUREMENT_USER)

    response = client.post(
        f"/api/v1/supplier-contracts/{created['contract_id']}/activate",
    )

    assert response.status_code in (200, 201)

    response = client.get(
        f"/api/v1/supplier-contracts/{created['contract_id']}/history",
    )

    assert response.status_code == 200

    history = response.json()

    assert any(
        item["to_status"] == "active"
        for item in history
    )


def test_contract_history_contains_renewal():
    created = create_contract()

    authenticate_as(PROCUREMENT_USER)

    activate_response = client.post(
        f"/api/v1/supplier-contracts/{created['contract_id']}/activate",
    )

    assert activate_response.status_code in (200, 201)

    renewal_response = client.post(
        f"/api/v1/supplier-contracts/{created['contract_id']}/renew",
        json={
            "new_start_date": "2027-10-01",
            "new_end_date": "2028-09-30",
            "reason": "Annual renewal",
        },
    )

    assert renewal_response.status_code in (200, 201)

    response = client.get(
        f"/api/v1/supplier-contracts/{created['contract_id']}/history",
    )

    assert response.status_code == 200

    history = response.json()

    assert len(history) >= 3


def test_supplier_can_view_own_contract_history():
    created = create_contract()

    authenticate_as(SUPPLIER_1_USER)

    response = client.get(
        f"/api/v1/supplier-contracts/{created['contract_id']}/history",
    )

    assert response.status_code == 200


def test_supplier_cannot_view_other_supplier_contract_history():
    authenticate_as(PROCUREMENT_USER)

    created = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(
            supplier_id=SUP002,
            contract_number="SC-SUP2-HISTORY",
        ),
    )

    assert created.status_code == 201

    contract_id = created.json()["contract_id"]

    authenticate_as(SUPPLIER_1_USER)

    response = client.get(
        f"/api/v1/supplier-contracts/{contract_id}/history",
    )

    assert response.status_code == 403

def test_contract_history_contains_term_update_audit():
    created = create_contract()

    authenticate_as(PROCUREMENT_USER)

    response = client.put(
        f"/api/v1/supplier-contracts/{created['contract_id']}",
        json={
            "payment_terms": "Net 45",
            "delivery_terms": "10 days",
            "minimum_order_value": 600000,
        },
    )

    assert response.status_code == 200

    response = client.get(
        f"/api/v1/supplier-contracts/{created['contract_id']}/history",
    )

    assert response.status_code == 200

    history = response.json()

    assert len(history) >= 2

    update_history = history[-1]

    assert update_history["contract_id"] == created["contract_id"]
    assert update_history["supplier_id"] == SUP001
    assert update_history["from_status"] == "draft"
    assert update_history["to_status"] == "draft"

    assert update_history["actor_id"] == str(
        PROCUREMENT_USER["user_id"]
    )
    assert update_history["actor_name"] == (
        PROCUREMENT_USER["full_name"]
    )
    assert update_history["role"] == (
        PROCUREMENT_USER["role"]
    )

    assert "Contract terms updated" in (
        update_history["reason"]
    )

    assert "payment_terms" in (
        update_history["reason"]
    )

    assert "delivery_terms" in (
        update_history["reason"]
    )

    assert "minimum_order_value" in (
        update_history["reason"]
    )

def test_contract_history_not_created_when_terms_do_not_change():
    created = create_contract()

    authenticate_as(PROCUREMENT_USER)

    first_response = client.get(
        f"/api/v1/supplier-contracts/{created['contract_id']}/history",
    )

    assert first_response.status_code == 200

    initial_history_count = len(
        first_response.json()
    )

    response = client.put(
        f"/api/v1/supplier-contracts/{created['contract_id']}",
        json={
            "payment_terms": "Net 30",
        },
    )

    assert response.status_code == 200

    second_response = client.get(
        f"/api/v1/supplier-contracts/{created['contract_id']}/history",
    )

    assert second_response.status_code == 200

    assert len(second_response.json()) == initial_history_count


# ============================================================
# AUTHENTICATION / AUTHORIZATION
# ============================================================

def test_create_contract_requires_authentication():
    clear_authentication()

    response = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(),
    )

    assert response.status_code == 401


def test_get_contract_requires_authentication():
    clear_authentication()

    response = client.get(
        "/api/v1/supplier-contracts/CNT-NOT-FOUND",
    )

    assert response.status_code == 401


def test_list_contracts_requires_authentication():
    clear_authentication()

    response = client.get(
        "/api/v1/supplier-contracts",
    )

    assert response.status_code == 401


def test_supplier_cannot_create_contract():
    authenticate_as(SUPPLIER_1_USER)

    response = client.post(
        "/api/v1/supplier-contracts",
        json=contract_payload(),
    )

    assert response.status_code == 403


def test_supplier_cannot_update_contract():
    created = create_contract()

    authenticate_as(SUPPLIER_1_USER)

    response = client.put(
        f"/api/v1/supplier-contracts/{created['contract_id']}",
        json={
            "title": "Supplier Should Not Update This",
        },
    )

    assert response.status_code == 403


def test_supplier_cannot_activate_contract():
    created = create_contract()

    authenticate_as(SUPPLIER_1_USER)

    response = client.post(
        f"/api/v1/supplier-contracts/{created['contract_id']}/activate",
    )

    assert response.status_code == 403


def test_supplier_cannot_renew_contract():
    created = create_contract()

    authenticate_as(SUPPLIER_1_USER)

    response = client.post(
        f"/api/v1/supplier-contracts/{created['contract_id']}/renew",
        json={
            "new_start_date": "2027-10-01",
            "new_end_date": "2028-09-30",
        },
    )

    assert response.status_code == 403


# ============================================================
# ROUTE ORDER REGRESSION
# ============================================================

def test_expiring_route_is_not_treated_as_contract_id():
    authenticate_as(PROCUREMENT_USER)

    response = client.get(
        "/api/v1/supplier-contracts/expiring",
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ============================================================
# CONTRACT LIFECYCLE INTEGRATION
# ============================================================

def test_complete_contract_lifecycle():
    created = create_contract()

    assert created["status"] == "draft"

    authenticate_as(PROCUREMENT_USER)

    activate_response = client.post(
        f"/api/v1/supplier-contracts/{created['contract_id']}/activate",
    )

    assert activate_response.status_code in (200, 201)
    assert activate_response.json()["status"] == "active"

    get_response = client.get(
        f"/api/v1/supplier-contracts/{created['contract_id']}",
    )

    assert get_response.status_code == 200
    assert get_response.json()["status"] == "active"

    renewal_response = client.post(
        f"/api/v1/supplier-contracts/{created['contract_id']}/renew",
        json={
            "new_start_date": "2027-10-01",
            "new_end_date": "2028-09-30",
            "reason": "Annual contract renewal",
        },
    )

    assert renewal_response.status_code in (200, 201)
    assert renewal_response.json()["status"] == "active"

    final_response = client.get(
        f"/api/v1/supplier-contracts/{created['contract_id']}",
    )

    assert final_response.status_code == 200

    final_data = final_response.json()

    assert final_data["status"] == "active"
    assert final_data["start_date"] == "2027-10-01"
    assert final_data["end_date"] == "2028-09-30"