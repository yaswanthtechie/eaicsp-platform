from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str  # required: fail loudly if missing
    TEST_DATABASE_URL: str | None = None  # only the test suite needs this
    PLATFORM_AUTH_URL: str = "http://localhost:8005"
    COMPLIANCE_SERVICE_URL: str = "http://localhost:8003"
    # Supplier has no country column yet; every supplier is
    # screened with this country until one is added.
    DEFAULT_SUPPLIER_COUNTRY: str = "India"
    # z-score for network safety stock (1.65 ~ 95% service level).
    NETWORK_SERVICE_LEVEL_Z: float = 1.65
    # Forecasts older than this fall back to sales history.
    FORECAST_MAX_AGE_DAYS: int = 35

    # Service API key issued by Platform for service-to-service calls (R15-RH1, R15-B6).
    # Used for outbound service-to-service calls to Forecast Serving and Compliance.
    # Set via INVENTORY_SERVICE_API_KEY env var. Never commit a real key.
    INVENTORY_SERVICE_API_KEY: str = ""

    # Forecast Service integration (Flow A, blueprint section 4)
    FORECAST_SERVICE_URL: str = "http://localhost:8007"
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

    # Optional local folder with canonical client staging CSVs (R15-B8).
    CLIENT_STAGING_DIR: str | None = None
    DEFAULT_SAFETY_STOCK: int = 10

    # Dynamic Service-Level Safety Stock (R16-B1)
    USE_DYNAMIC_SAFETY_STOCK: bool = False
    SAFETY_STOCK_DEMAND_HISTORY_WEEKS: int = 12
    SAFETY_STOCK_MIN_DEMAND_DAYS: int = 14
    SAFETY_STOCK_MIN_PO_COUNT: int = 3
    ABC_REVENUE_A_THRESHOLD: float = 0.80
    ABC_REVENUE_B_THRESHOLD: float = 0.95
    XYZ_CV_X_THRESHOLD: float = 0.50
    XYZ_CV_Y_THRESHOLD: float = 1.00
    SAFETY_STOCK_DEFAULT_LEAD_TIME_DAYS: float = 1.0
    SAFETY_STOCK_SERVICE_LEVELS: dict[str, float] = Field(
        default_factory=lambda: {
            "AX": 0.98,
            "AY": 0.96,
            "AZ": 0.94,
            "BX": 0.95,
            "BY": 0.93,
            "BZ": 0.90,
            "CX": 0.92,
            "CY": 0.90,
            "CZ": 0.90,
        }
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @field_validator("SAFETY_STOCK_SERVICE_LEVELS", mode="after")
    @classmethod
    def validate_service_levels(cls, v: dict[str, float]) -> dict[str, float]:
        for k, sl in v.items():
            if not (0.0 < sl < 1.0):
                raise ValueError(
                    f"Service level for {k} must be strictly between 0 and 1, got {sl}"
                )
        return v

    @field_validator("DATABASE_URL", "TEST_DATABASE_URL", mode="after")
    @classmethod
    def normalize_db_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v.startswith("postgresql+psycopg://"):
            return v.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
        if v.startswith("postgresql://") and not v.startswith("postgresql+psycopg2://"):
            return v.replace("postgresql://", "postgresql+psycopg2://", 1)
        return v


# DATABASE_URL has no default on purpose; pydantic-settings reads it from the
# environment or .env at runtime, which mypy cannot see.
settings = Settings()  # type: ignore[call-arg]
DEFAULT_SAFETY_STOCK = settings.DEFAULT_SAFETY_STOCK
