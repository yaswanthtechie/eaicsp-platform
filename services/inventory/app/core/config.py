from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    TEST_DATABASE_URL: str
    PLATFORM_AUTH_URL: str = "http://localhost:8005"
    COMPLIANCE_SERVICE_URL: str = "http://localhost:8003"
    PO_AUTO_APPROVAL_THRESHOLD: float = 1000.0
    # Supplier has no country column yet; every supplier is
    # screened with this country until one is added.
    DEFAULT_SUPPLIER_COUNTRY: str = "India"
    # z-score for network safety stock (1.65 ~ 95% service level).
    NETWORK_SERVICE_LEVEL_Z: float = 1.65
    # Forecasts older than this fall back to sales history.
    FORECAST_MAX_AGE_DAYS: int = 35

    model_config = SettingsConfigDict(
        env_file=".env"
    )

    @field_validator("DATABASE_URL", "TEST_DATABASE_URL", mode="after")
    @classmethod
    def normalize_db_url(cls, v: str) -> str:
        if v.startswith("postgresql+psycopg://"):
            return v.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
        return v


settings = Settings()