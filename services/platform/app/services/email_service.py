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
    def send_mfa_otp(
        email: str,
        otp: str,
    ) -> None:
        """
        Mock MFA OTP delivery.

       this only logs the OTP instead of
        sending a real email.
        """
        logger.info(
            "MOCK MFA OTP EMAIL | "
            "recipient=%s | otp=%s",
            email,
            otp,
        )