import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core import config as app_config
from app.database import SessionLocal
from app.main import app
from app.services import mfa_service
from app.services.rate_limit_service import MFA_ABUSE, check_rate_limit

client = TestClient(app)

ANALYST = {"username": "analyst@company.com", "password": "analyst@1234"}
CEO = {"username": "ceo@company.com", "password": "ceocompany@123"}
SUPPLIER = {"username": "supplier@company.com", "password": "supplier@123"}


def _token(creds):
    r = client.post("/api/v1/auth/login", data=creds)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def mfa_on(monkeypatch):
    monkeypatch.setattr(app_config, "MFA_ENABLED", True)
    monkeypatch.setattr(app_config, "MFA_MOCK_OTP", "246810")


@pytest.fixture
def sso_on(monkeypatch):
    monkeypatch.setattr(app_config, "MOCK_SSO_ENABLED", True)
    monkeypatch.setattr(app_config, "MOCK_SSO_SECRET",  "test-sso-secret-0123456789abcdef-xyz",)

def _export(admin_token):
    r = client.get(
        "/api/v1/admin/audit/export",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    return r.text


# ---------------- MFA ----------------

def test_login_without_mfa_still_returns_tokens():
    r = client.post("/api/v1/auth/login", data=ANALYST)
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_mfa_end_to_end_and_audited(monkeypatch):
    admin = _token(CEO)                       # before MFA is switched on
    monkeypatch.setattr(app_config, "MFA_ENABLED", True)
    monkeypatch.setattr(app_config, "MFA_MOCK_OTP", "246810")

    r = client.post("/api/v1/auth/login", data=ANALYST)
    assert r.json()["mfa_required"] is True
    challenge = r.json()["challenge_id"]

    wrong = client.post("/api/v1/auth/mfa/verify", json={"challenge_id": challenge, "otp": "000000"})
    assert wrong.status_code == 401

    ok = client.post("/api/v1/auth/mfa/verify", json={"challenge_id": challenge, "otp": "246810"})
    assert ok.status_code == 200
    assert "access_token" in ok.json()

    reuse = client.post("/api/v1/auth/mfa/verify", json={"challenge_id": challenge, "otp": "246810"})
    assert reuse.status_code == 401

    csv_text = _export(admin)
    assert "MFA_VERIFIED" in csv_text
    assert "MFA_FAILED" in csv_text


def test_challenge_destroyed_after_max_wrong_attempts(mfa_on):
    challenge_id, _ = mfa_service.create_mfa_challenge(user_id=1)

    for _ in range(mfa_service.MAX_OTP_ATTEMPTS):
        assert mfa_service.verify_mfa_challenge(challenge_id, "000000") is None

    # Correct OTP no longer works: the challenge is gone.
    assert mfa_service.verify_mfa_challenge(challenge_id, "246810") is None


def test_otp_is_random_when_no_mock_otp(monkeypatch):
    monkeypatch.setattr(app_config, "MFA_MOCK_OTP", None)
    otps = {mfa_service.create_mfa_challenge(user_id=1)[1] for _ in range(20)}
    assert len(otps) > 1


# ---------------- Rate limiting ----------------

def test_rate_limit_is_per_ip_not_global():
    db = SessionLocal()
    try:
        kwargs = dict(db=db, endpoint="/api/v1/auth/mfa/verify", abuse_event_type=MFA_ABUSE)

        for _ in range(5):
            check_rate_limit(ip_address="10.0.0.1", **kwargs)

        with pytest.raises(HTTPException) as exc:
            check_rate_limit(ip_address="10.0.0.1", **kwargs)
        assert exc.value.status_code == 429

        # A different client is NOT affected.
        check_rate_limit(ip_address="10.0.0.2", **kwargs)
    finally:
        db.close()


# ---------------- SSO ----------------

def test_sso_accepts_signed_assertion_and_is_audited(sso_on):
    from app.services.sso_service import create_mock_sso_assertion

    admin = _token(CEO)
    r = client.post(
        "/api/v1/auth/sso/login",
        json={"provider": "mock-enterprise-sso", "assertion": create_mock_sso_assertion("enterprise-002")},
    )
    assert r.status_code == 200
    assert r.json()["auth_type"] == "federated-sso"
    assert "SSO_LOGIN" in _export(admin)


def test_sso_rejects_assertion_signed_with_wrong_secret(sso_on, monkeypatch):
    from app.services.sso_service import create_mock_sso_assertion

    forged = create_mock_sso_assertion("enterprise-001")
    monkeypatch.setattr(app_config, "MOCK_SSO_SECRET", "different-sso-secret-0123456789abcdef")

    r = client.post("/api/v1/auth/sso/login", json={"provider": "mock-enterprise-sso", "assertion": forged})
    assert r.status_code == 401


def test_sso_rejects_plain_client_fields():
    # The old request shape (email/full_name/external_id) must not work.
    r = client.post(
        "/api/v1/auth/sso/login",
        json={
            "provider": "mock-enterprise-sso",
            "email": "ceo@company.com",
            "full_name": "CEO User",
            "external_id": "enterprise-001",
        },
    )
    assert r.status_code in (404, 422)


def test_sso_disabled_by_default():
    r = client.post("/api/v1/auth/sso/login", json={"provider": "mock-enterprise-sso", "assertion": "x"})
    assert r.status_code == 404

def test_sso_refuses_blank_secret(monkeypatch):
    monkeypatch.setattr(app_config, "MOCK_SSO_ENABLED", True)
    monkeypatch.setattr(app_config, "MOCK_SSO_SECRET", "")
    from jose import jwt
    forged = jwt.encode(
        {"iss": "mock-enterprise-sso", "aud": "eaicsp-platform", "sub": "x",
         "email": "ceo@company.com", "exp": 9999999999},
        "", algorithm="HS256",
    )
    r = client.post("/api/v1/auth/sso/login", json={"provider": "mock-enterprise-sso", "assertion": forged})
    assert r.status_code == 503

def test_env_example_does_not_ship_a_usable_sso_secret():
    from pathlib import Path

    env_example = Path(__file__).resolve().parents[1] / ".env.example"
    for line in env_example.read_text(encoding="utf-8").splitlines():
        if line.startswith("MOCK_SSO_SECRET="):
            # Must be blank so the startup check forces a real secret.
            assert line.split("=", 1)[1].strip() == ""
            
# ---------------- Audit export / abuse dashboard ----------------

def test_audit_export_has_compliance_columns():
    header = _export(_token(CEO)).splitlines()[0]
    assert header == "timestamp,actor_id,actor_email,action,outcome,ip_address,details"


def test_supplier_cannot_export_or_view_abuse_dashboard():
    token = _token(SUPPLIER)
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/v1/admin/audit/export", headers=headers).status_code == 403
    assert client.get("/api/v1/admin/abuse/dashboard", headers=headers).status_code == 403

def test_audit_export_limit_is_applied():
    admin = _token(CEO)
    _token(CEO)  # at least two audit rows
    r = client.get("/api/v1/admin/audit/export?limit=1", headers={"Authorization": f"Bearer {admin}"})
    assert len(r.text.strip().splitlines()) == 2   # header + 1 row


def test_audit_export_json_format():
    admin = _token(CEO)
    r = client.get("/api/v1/admin/audit/export?output_format=json", headers={"Authorization": f"Bearer {admin}"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert {"timestamp", "actor_email", "action", "outcome"} <= set(r.json()[0])