from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./inventory.db"
    TEST_DATABASE_URL: str = "sqlite:///./test.db"
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

    # Redis Cache configuration
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL_SECONDS: int = 300

    # Kafka Broker configuration
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"

    # Outbox Relay background worker
    ENABLE_OUTBOX_RELAY: bool = False
    OUTBOX_RELAY_INTERVAL_SECONDS: float = 2.0

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @field_validator("DATABASE_URL", "TEST_DATABASE_URL", mode="after")
    @classmethod
    def normalize_db_url(cls, v: str) -> str:
        if v.startswith("postgresql+psycopg://"):
            return v.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
        if v.startswith("postgresql://") and not v.startswith("postgresql+psycopg2://"):
            return v.replace("postgresql://", "postgresql+psycopg2://", 1)
        return v


settings = Settings()
settings = Settings()