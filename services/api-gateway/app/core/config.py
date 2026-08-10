"""
Application configuration for the API Gateway.
"""

from typing import Dict

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    with sensible default values.
    """

    # --------------------------------------------------
    # Application
    # --------------------------------------------------

    APP_NAME: str = "API Gateway"
    VERSION: str = "1.0.0"
    DEBUG: bool = False

    # --------------------------------------------------
    # Downstream Service Routes
    # --------------------------------------------------

    SERVICE_ROUTES: Dict[str, str] = {
        "/api/v1/inventory": "http://localhost:8001",
        "/api/v1/shipments": "http://localhost:8002",
        "/api/v1/compliance": "http://localhost:8003",
        "/api/v1/purchase-orders": "http://localhost:8004",
        "/api/v1/auth": "http://localhost:8005",
        "/api/v1/supplier-risk": "http://localhost:8006",

        # Dummy service routes used for testing
        "/timeout": "http://localhost:8001",
        "/error": "http://localhost:8001",
    }

    # --------------------------------------------------
    # HTTP Client Configuration
    # --------------------------------------------------

    TIMEOUT_SECONDS: int = 5
    # MAX_RETRIES: number of retries to attempt on retryable failures (e.g. 2 → original + 2 retries)
    MAX_RETRIES: int = 2

    # --------------------------------------------------
    # Environment Configuration
    # --------------------------------------------------

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


# Singleton settings instance
settings = Settings()