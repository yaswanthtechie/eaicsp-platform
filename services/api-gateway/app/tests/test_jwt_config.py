"""
Focused tests for SECRET_KEY JWT configuration integration.

Verifies:
- Settings instantiation fails loudly when SECRET_KEY is missing (no fallback)
- JWTs signed with the configured SECRET_KEY decode correctly
- JWTs signed with a different secret are rejected (signature mismatch)
"""

import os

import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings

try:
    import jwt
except ImportError:
    jwt = None


pytestmark = pytest.mark.skipif(jwt is None, reason="PyJWT is required for JWT config tests")


class TestSecretKeyRequirement:
    def test_settings_requires_secret_key_no_default(self, monkeypatch):
        """
        Settings instantiation must raise ValidationError when SECRET_KEY
        is absent from the environment — no silent fallback or default.
        """
        monkeypatch.delenv("SECRET_KEY", raising=False)

        with pytest.raises(ValidationError) as excinfo:
            Settings(_env_file=None)

        errors = excinfo.value.errors()
        fields_missing = [err.get("loc") for err in errors]
        assert ("SECRET_KEY",) in fields_missing or any(
            "SECRET_KEY" in loc for loc in fields_missing
        ), f"Expected SECRET_KEY validation error, got: {errors}"

    def test_settings_succeeds_with_secret_key_present(self, monkeypatch):
        """
        Settings instantiation succeeds normally when SECRET_KEY is set.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret-key-configured-for-testing-32bytes")
        monkeypatch.setenv("JWT_ALGORITHM", "HS256")

        fresh = Settings(_env_file=None)
        assert fresh.SECRET_KEY == "test-secret-key-configured-for-testing-32bytes"
        assert fresh.JWT_ALGORITHM == "HS256"


class TestJwtSecretRoundTrip:
    def test_jwt_signed_with_configured_secret_decodes_successfully(self):
        """
        A JWT signed using settings.SECRET_KEY must decode successfully
        using the gateway configuration (same secret + HS256).
        """
        payload = {"user_id": "u_123", "role": "admin", "sub": "u_123"}
        token = jwt.encode(
            payload,
            settings.SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )

        decoded = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )

        assert decoded["user_id"] == "u_123"
        assert decoded["role"] == "admin"

    def test_jwt_signed_with_different_secret_is_rejected(self):
        """
        A JWT signed using a *different* secret must be rejected when
        decoded with the gateway's configured SECRET_KEY.

        This is the core security check: mismatched secrets → signature error.
        """
        payload = {"user_id": "u_999", "role": "admin"}
        wrong_secret = "another-completely-different-secret-value-32bytes"

        token = jwt.encode(payload, wrong_secret, algorithm=settings.JWT_ALGORITHM)

        with pytest.raises(jwt.PyJWTError):
            jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )

    def test_jwt_signed_with_issuer_style_secret_round_trip(self):
        """
        Simulates the platform-issuer → gateway-verifier integration scenario.

        A separate Settings instance (stand-in for the platform token issuer)
        signs a token with its own SECRET_KEY value. When the gateway
        Settings.SECRET_KEY matches, the token verifies successfully.
        """
        issuer_secret = "shared-secret-between-platform-and-gateway-32bytes"

        os.environ["SECRET_KEY"] = issuer_secret
        issuer_settings = Settings()
        gateway_settings = Settings()

        assert issuer_settings.SECRET_KEY == gateway_settings.SECRET_KEY == issuer_secret

        payload = {"sub": "platform-issued-token", "user_id": "p_1"}
        token = jwt.encode(
            payload,
            issuer_settings.SECRET_KEY,
            algorithm=issuer_settings.JWT_ALGORITHM,
        )

        decoded = jwt.decode(
            token,
            gateway_settings.SECRET_KEY,
            algorithms=[gateway_settings.JWT_ALGORITHM],
        )

        assert decoded["sub"] == "platform-issued-token"

    def test_issuer_gateway_secret_mismatch_rejects_token(self):
        """
        When the issuer's SECRET_KEY differs from the gateway's SECRET_KEY,
        the gateway must refuse the token (this is the bug being fixed).
        """
        old_secret = os.environ.get("SECRET_KEY")
        try:
            os.environ["SECRET_KEY"] = "platform-issuer-secret-key-min-32-bytes-long-1234"
            issuer_settings = Settings()

            os.environ["SECRET_KEY"] = "gateway-verifier-secret-key-min-32-bytes-long-5678"
            gateway_settings = Settings()

            payload = {"sub": "should-not-verify"}
            token = jwt.encode(
                payload,
                issuer_settings.SECRET_KEY,
                algorithm=issuer_settings.JWT_ALGORITHM,
            )

            with pytest.raises(jwt.PyJWTError):
                jwt.decode(
                    token,
                    gateway_settings.SECRET_KEY,
                    algorithms=[gateway_settings.JWT_ALGORITHM],
                )
        finally:
            if old_secret is not None:
                os.environ["SECRET_KEY"] = old_secret
            else:
                os.environ.pop("SECRET_KEY", None)
