from datetime import datetime, timedelta, timezone
import secrets
import uuid

# ---------------------------------------------------------
# Mock MFA configuration
# ---------------------------------------------------------

OTP_EXPIRE_MINUTES = 5
# Fixed OTP for development/demo purposes.
# DO NOT use a fixed OTP in production.
MOCK_OTP = "123456"
# In-memory MFA challenge store.
# This is intentionally a mock implementation for R9-R11.
# In production, use Redis or a database so that challenges
# work correctly across multiple Platform Service instances.
_mfa_challenges = {}

# ---------------------------------------------------------
# Create MFA challenge
# ---------------------------------------------------------

def create_mfa_challenge(user_id: int) -> tuple[str, str]:
    """
    Create a mock MFA challenge.

    Returns:
        tuple[str, str]:
            challenge_id, otp
    """

    challenge_id = str(uuid.uuid4())

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(minutes=OTP_EXPIRE_MINUTES)
    )

    _mfa_challenges[challenge_id] = {
        "user_id": user_id,
        "otp": MOCK_OTP,
        "expires_at": expires_at,
        "verified": False,
    }

    return challenge_id, MOCK_OTP

# ---------------------------------------------------------
# Verify MFA challenge
# ---------------------------------------------------------

def verify_mfa_challenge(
    challenge_id: str,
    otp: str,
) -> int | None:
    """
    Verify an MFA challenge.

    Returns:
        user_id:
            If the OTP is valid.

        None:
            If the challenge is invalid, expired,
            already used, or the OTP is incorrect.
    """

    challenge = _mfa_challenges.get(challenge_id)

    if challenge is None:
        return None

    # Prevent replay of an already-used challenge.
    if challenge["verified"]:
        return None

    # Check expiration.
    now = datetime.now(timezone.utc)

    if now > challenge["expires_at"]:
        _mfa_challenges.pop(challenge_id, None)
        return None

    # Constant-time OTP comparison.
    if not secrets.compare_digest(
        str(otp),
        str(challenge["otp"]),
    ):
        return None

    user_id = challenge["user_id"]

    # Mark as verified before removing it.
    challenge["verified"] = True

    # Make the challenge single-use.
    _mfa_challenges.pop(challenge_id, None)

    return user_id