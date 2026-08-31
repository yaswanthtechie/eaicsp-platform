
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
