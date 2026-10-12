from datetime import datetime, timedelta, timezone
import secrets
import threading
import uuid

from app.core import config as app_config

OTP_EXPIRE_MINUTES = 5
MAX_OTP_ATTEMPTS = 5

# In-memory challenge store (mock for R9-R11). Production would use
# Redis/DB so challenges work across multiple Platform instances.
_mfa_challenges: dict[str, dict] = {}
_lock = threading.Lock()


def _generate_otp() -> str:
    # Fixed OTP ONLY when explicitly configured for dev/demo.
    if app_config.MFA_MOCK_OTP:
        return app_config.MFA_MOCK_OTP
    return f"{secrets.randbelow(10**6):06d}"


def create_mfa_challenge(user_id: int) -> tuple[str, str]:
    challenge_id = str(uuid.uuid4())
    otp = _generate_otp()

    with _lock:
        _mfa_challenges[challenge_id] = {
            "user_id": user_id,
            "otp": otp,
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES),
            "attempts": 0,
        }

    return challenge_id, otp


def verify_mfa_challenge(challenge_id: str, otp: str) -> int | None:
    """
    Returns user_id on success, otherwise None.

    A challenge is single-use, expires after OTP_EXPIRE_MINUTES, and is
    destroyed after MAX_OTP_ATTEMPTS wrong guesses.
    """
    with _lock:
        challenge = _mfa_challenges.get(challenge_id)

        if challenge is None:
            return None

        if datetime.now(timezone.utc) > challenge["expires_at"]:
            _mfa_challenges.pop(challenge_id, None)
            return None

        if not secrets.compare_digest(str(otp), str(challenge["otp"])):
            challenge["attempts"] += 1
            if challenge["attempts"] >= MAX_OTP_ATTEMPTS:
                _mfa_challenges.pop(challenge_id, None)
            return None

        # Success: single use.
        _mfa_challenges.pop(challenge_id, None)
        return challenge["user_id"]