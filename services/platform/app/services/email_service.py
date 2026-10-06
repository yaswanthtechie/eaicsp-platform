import logging
logger = logging.getLogger(__name__)

class MockEmailService:

    @staticmethod
    def send_password_reset_email(
        email: str,
        reset_token: str,
    ) -> None:
        logger.info(
            "MOCK PASSWORD RESET EMAIL | "
            "recipient=%s | reset_token=%s",
            email,
            reset_token,
        )

    @staticmethod
    def send_mfa_otp(email: str, otp: str) -> None:
        """
        Mock MFA OTP delivery.

        The OTP itself is never logged, it is a live credential.
        """
        logger.info("MOCK MFA OTP EMAIL | recipient=%s | otp=<redacted>", email)