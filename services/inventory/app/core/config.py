from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str                      # required: fail loudly if missing
    TEST_DATABASE_URL: str | None = None   # only the test suite needs this

    PLATFORM_AUTH_URL: str = "http://localhost:8005"
    COMPLIANCE_SERVICE_URL: str = "http://localhost:8003"
    FORECAST_SERVICE_URL: str = "http://localhost:8006"

    # Supplier has no country column yet; every supplier is
    # screened with this country until one is added.
    DEFAULT_SUPPLIER_COUNTRY: str = "India"

    # z-score for network safety stock (1.65 ~ 95% service level).
    NETWORK_SERVICE_LEVEL_Z: float = 1.65

    # Forecasts older than this fall back to sales history.
    FORECAST_MAX_AGE_DAYS: int = 35

    # Forecast Service integration (Flow A, blueprint section 4)
    FORECAST_SERVICE_URL: str = "http://localhost:8007"
    # Set via env (service key issued by Platform). Never commit a real key.
    FORECAST_SERVICE_API_KEY: str = ""
    FORECAST_TIMEOUT_SECONDS: float = 2.0
    FORECAST_RETRY_COUNT: int = 1
    FORECAST_HORIZON_DAYS: int = 30
    FORECAST_FALLBACK_DAYS: int = 28

    # Redis Cache configuration
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL_SECONDS: int = 300

    # Kafka Broker configuration
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_CONSUMER_GROUP: str = "inventory-service"
    COMPLIANCE_STATUS_CHANGED_TOPIC: str = "compliance.supplier.status_changed"
    COMPLIANCE_DLQ_TOPIC: str = "compliance.supplier.status_changed.dlq"
    COMPLIANCE_CONSUMER_INTERVAL_SECONDS: float = 1.0

    # PO Acknowledged Consumer (Flow B)
    PO_ACKNOWLEDGED_TOPIC: str = "supplierportal.po.acknowledged"
    PO_ACKNOWLEDGED_CONSUMER_GROUP: str = "inventory-po-acknowledged-consumer"
    PO_ACKNOWLEDGED_DLQ_TOPIC: str = "supplierportal.po.acknowledged.dlq"
    PO_ACKNOWLEDGED_CONSUMER_INTERVAL_SECONDS: float = 1.0

    # Outbox Relay background worker
    ENABLE_OUTBOX_RELAY: bool = False
    OUTBOX_RELAY_INTERVAL_SECONDS: float = 2.0
    # Outbox: after this many failed publishes an event becomes DEAD
    OUTBOX_MAX_RETRIES: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @field_validator("DATABASE_URL", "TEST_DATABASE_URL", mode="after")
    @classmethod
    def normalize_db_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v.startswith("postgresql+psycopg://"):
            return v.replace(
                "postgresql+psycopg://",
                "postgresql+psycopg2://",
                1,
            )
        if v.startswith("postgresql://") and not v.startswith(
            "postgresql+psycopg2://"
        ):
            return v.replace(
                "postgresql://",
                "postgresql+psycopg2://",
                1,
            )
        return v


settings = Settings()
