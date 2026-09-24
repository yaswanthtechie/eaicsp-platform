from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    TEST_DATABASE_URL: str
    PLATFORM_AUTH_URL: str = "http://localhost:8005"
    COMPLIANCE_SERVICE_URL: str = "http://localhost:8000"
    PO_AUTO_APPROVAL_THRESHOLD: float = 1000.0

    model_config = SettingsConfigDict(
        env_file=".env"
    )


settings = Settings()