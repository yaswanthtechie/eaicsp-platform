import hashlib
from datetime import UTC, datetime, timedelta

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.service_auth import (
    generate_service_api_key,
    hash_service_api_key,
    require_service,
)
from app.database import SessionLocal
from app.main import app
from app.models.service_api_keys import ServiceAPIKey
from app.seed import REQUIRED_SERVICE_KEYS, seed_service_api_keys

client = TestClient(app)  # type: ignore[arg-type]


def login_as_admin():
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "ceo@company.com",
            "password": "ceocompany@123",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def login_as_non_admin():
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "supplier@company.com",
            "password": "supplier@123",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------
# 1. Valid service API key accepted
# ------------------------------------------------------------
def test_valid_service_api_key_accepted():
    admin_token = login_as_admin()
    create_res = client.post(
        "/api/v1/admin/service-keys",
        headers=auth_header(admin_token),
        json={"service_name": "test-valid-accept"},
    )
    assert create_res.status_code == 201
    api_key = create_res.json()["api_key"]

    verify_res = client.post(
        "/api/v1/auth/service-verify",
        headers={"X-API-Key": api_key},
    )
    assert verify_res.status_code == 200
    data = verify_res.json()
    assert data["authenticated"] is True
    assert data["service"] == "test-valid-accept"
    assert data["auth_type"] == "api_key"


# ------------------------------------------------------------
# 2. Missing API key rejected with 401
# ------------------------------------------------------------
def test_missing_api_key_rejected_with_401():
    response = client.post("/api/v1/auth/service-verify")
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing service API key"


# ------------------------------------------------------------
# 3. Wrong API key rejected with 401
# ------------------------------------------------------------
def test_wrong_api_key_rejected_with_401():
    response = client.post(
        "/api/v1/auth/service-verify",
        headers={"X-API-Key": "sk_invalid_wrong_secret_key_12345"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid service API key"


# ------------------------------------------------------------
# 4. Revoked API key rejected with 401
# ------------------------------------------------------------
def test_revoked_api_key_rejected_with_401():
    admin_token = login_as_admin()
    create_res = client.post(
        "/api/v1/admin/service-keys",
        headers=auth_header(admin_token),
        json={"service_name": "test-revoke-key"},
    )
    assert create_res.status_code == 201
    key_id = create_res.json()["id"]
    api_key = create_res.json()["api_key"]

    # Verify works before revocation
    before_res = client.post(
        "/api/v1/auth/service-verify",
        headers={"X-API-Key": api_key},
    )
    assert before_res.status_code == 200

    # Revoke key
    revoke_res = client.delete(
        f"/api/v1/admin/service-keys/{key_id}",
        headers=auth_header(admin_token),
    )
    assert revoke_res.status_code == 200

    # Verification immediately fails after revocation
    after_res = client.post(
        "/api/v1/auth/service-verify",
        headers={"X-API-Key": api_key},
    )
    assert after_res.status_code == 401
    assert "inactive or revoked" in after_res.json()["detail"].lower()


# ------------------------------------------------------------
# 5. Expired key rejected if expiry is supported
# ------------------------------------------------------------
def test_expired_key_rejected_with_401():
    db = SessionLocal()
    try:
        raw_key = generate_service_api_key()
        key_hash = hash_service_api_key(raw_key)
        past_date = datetime.now(UTC) - timedelta(days=1)

        expired_key = ServiceAPIKey(
            service_name="test-expired-service",
            key_hash=key_hash,
            is_active=True,
            expires_at=past_date,
        )
        db.add(expired_key)
        db.commit()

        response = client.post(
            "/api/v1/auth/service-verify",
            headers={"X-API-Key": raw_key},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Service API key expired"
    finally:
        db.close()


# ------------------------------------------------------------
# 6. Inactive key rejected
# ------------------------------------------------------------
def test_inactive_key_rejected_with_401():
    db = SessionLocal()
    try:
        raw_key = generate_service_api_key()
        key_hash = hash_service_api_key(raw_key)

        inactive_key = ServiceAPIKey(
            service_name="test-inactive-service",
            key_hash=key_hash,
            is_active=False,
            expires_at=None,
        )
        db.add(inactive_key)
        db.commit()

        response = client.post(
            "/api/v1/auth/service-verify",
            headers={"X-API-Key": raw_key},
        )
        assert response.status_code == 401
        assert "inactive or revoked" in response.json()["detail"].lower()
    finally:
        db.close()


# ------------------------------------------------------------
# 7. Valid but unauthorized service rejected with 403
# ------------------------------------------------------------
def test_valid_but_unauthorized_service_rejected_with_403():
    # Setup test FastAPI app with protected endpoint
    test_app = FastAPI()

    inventory_guard = require_service("inventory")

    @test_app.get("/internal/inventory-only")
    def inventory_only_route(service: dict = Depends(inventory_guard)):  # noqa: B008
        return {"authorized_service": service["service"]}

    test_client = TestClient(test_app)

    admin_token = login_as_admin()

    # Issue inventory key (authorized)
    inv_res = client.post(
        "/api/v1/admin/service-keys",
        headers=auth_header(admin_token),
        json={"service_name": "inventory"},
    )
    assert inv_res.status_code == 201
    inv_key = inv_res.json()["api_key"]

    # Issue supplier-portal key (unauthorized for inventory endpoint)
    sup_res = client.post(
        "/api/v1/admin/service-keys",
        headers=auth_header(admin_token),
        json={"service_name": "supplier-portal"},
    )
    assert sup_res.status_code == 201
    sup_key = sup_res.json()["api_key"]

    # Authorized caller succeeds
    ok_res = test_client.get(
        "/internal/inventory-only",
        headers={"X-API-Key": inv_key},
    )
    assert ok_res.status_code == 200
    assert ok_res.json()["authorized_service"] == "inventory"

    # Unauthorized caller rejected with 403
    unauth_res = test_client.get(
        "/internal/inventory-only",
        headers={"X-API-Key": sup_key},
    )
    assert unauth_res.status_code == 403
    assert "not authorized" in unauth_res.json()["detail"].lower()


# ------------------------------------------------------------
# 8. Database stores hash, not raw key
# ------------------------------------------------------------
def test_database_stores_hash_not_raw_key():
    admin_token = login_as_admin()
    create_res = client.post(
        "/api/v1/admin/service-keys",
        headers=auth_header(admin_token),
        json={"service_name": "test-hash-storage"},
    )
    assert create_res.status_code == 201
    body = create_res.json()
    raw_key = body["api_key"]
    key_id = body["id"]

    db = SessionLocal()
    try:
        record = db.query(ServiceAPIKey).filter(ServiceAPIKey.id == key_id).first()
        assert record is not None
        assert record.key_hash != raw_key
        assert record.key_hash == hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        assert not hasattr(record, "api_key")
    finally:
        db.close()


# ------------------------------------------------------------
# 9. Last-used timestamp updated
# ------------------------------------------------------------
def test_last_used_timestamp_updated():
    admin_token = login_as_admin()
    create_res = client.post(
        "/api/v1/admin/service-keys",
        headers=auth_header(admin_token),
        json={"service_name": "test-timestamp-tracking"},
    )
    assert create_res.status_code == 201
    raw_key = create_res.json()["api_key"]
    key_id = create_res.json()["id"]

    db = SessionLocal()
    try:
        record = db.query(ServiceAPIKey).filter(ServiceAPIKey.id == key_id).first()
        assert record.last_used_at is None

        # Verify key
        verify_res = client.post(
            "/api/v1/auth/service-verify",
            headers={"X-API-Key": raw_key},
        )
        assert verify_res.status_code == 200

        db.refresh(record)
        assert record.last_used_at is not None
        first_used_at = record.last_used_at

        # Verify second time
        verify_res2 = client.post(
            "/api/v1/auth/service-verify",
            headers={"X-API-Key": raw_key},
        )
        assert verify_res2.status_code == 200
        db.refresh(record)
        assert record.last_used_at >= first_used_at
    finally:
        db.close()


# ------------------------------------------------------------
# 10. All four required caller identities are registered
# ------------------------------------------------------------
def test_all_four_required_caller_identities_registered():
    db = SessionLocal()
    try:
        seed_service_api_keys(db, require_env=False)
        expected_mapping = {
            "inventory": "INVENTORY_SERVICE_API_KEY",
            "supplier-portal": "SUPPLIER_PORTAL_SERVICE_API_KEY",
            "gateway-bff": "GATEWAY_BFF_SERVICE_API_KEY",
            "forecast-serving": "FORECAST_SERVING_SERVICE_API_KEY",
        }
        assert REQUIRED_SERVICE_KEYS == expected_mapping

        # Verify DB records exist for all 4 canonical identities
        for service_name in expected_mapping:
            record = (
                db.query(ServiceAPIKey)
                .filter(ServiceAPIKey.service_name == service_name)
                .first()
            )
            assert record is not None, f"Missing record for {service_name}"
            assert record.is_active is True
    finally:
        db.close()


# ------------------------------------------------------------
# 11. Repeated seed does not create duplicate records (Idempotency)
# ------------------------------------------------------------
def test_repeated_seed_does_not_create_duplicate_records():
    db = SessionLocal()
    try:
        identities = [
            "inventory",
            "supplier-portal",
            "gateway-bff",
            "forecast-serving",
        ]
        # First seeding
        seed_service_api_keys(db, require_env=False)
        first_records = {
            k.service_name: (k.id, k.key_hash)
            for k in db.query(ServiceAPIKey)
            .filter(ServiceAPIKey.service_name.in_(identities))
            .all()
        }
        assert len(first_records) == 4

        # Second seeding (repeated execution)
        seed_service_api_keys(db, require_env=False)
        second_records = {
            k.service_name: (k.id, k.key_hash)
            for k in db.query(ServiceAPIKey)
            .filter(ServiceAPIKey.service_name.in_(identities))
            .all()
        }
        assert len(second_records) == 4

        # IDs and key hashes must not change or rotate unexpectedly
        for name in identities:
            assert first_records[name][0] == second_records[name][0]
            assert first_records[name][1] == second_records[name][1]
    finally:
        db.close()


# ------------------------------------------------------------
# 12. Existing Platform user JWT verification tests continue passing
# ------------------------------------------------------------
def test_existing_user_jwt_verification_continues_passing():
    admin_token = login_as_admin()

    # User JWT verification endpoint remains /api/v1/auth/verify
    verify_res = client.post(
        "/api/v1/auth/verify",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert verify_res.status_code == 200
    user_data = verify_res.json()
    assert user_data["valid"] is True
    assert user_data["email"] == "ceo@company.com"
    assert user_data["role"] == "ceo"

    # Invalid user JWT rejected with 401
    bad_res = client.post(
        "/api/v1/auth/verify",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )
    assert bad_res.status_code == 401


# ------------------------------------------------------------
# 13. Existing Platform admin authorization tests continue passing
# ------------------------------------------------------------
def test_existing_admin_authorization_enforced():
    supplier_token = login_as_non_admin()
    admin_token = login_as_admin()

    # Non-admin cannot create service keys (403)
    non_admin_create = client.post(
        "/api/v1/admin/service-keys",
        headers=auth_header(supplier_token),
        json={"service_name": "unauthorized-creation"},
    )
    assert non_admin_create.status_code == 403

    # Non-admin cannot list service keys (403)
    non_admin_list = client.get(
        "/api/v1/admin/service-keys",
        headers=auth_header(supplier_token),
    )
    assert non_admin_list.status_code == 403

    # Admin can list service keys (200)
    admin_list = client.get(
        "/api/v1/admin/service-keys",
        headers=auth_header(admin_token),
    )
    assert admin_list.status_code == 200
    assert isinstance(admin_list.json(), list)
