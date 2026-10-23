from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# ============================================================
# BASE DIRECTORY
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent


# ============================================================
# UPLOAD DIRECTORY
# ============================================================

UPLOAD_DIR = BASE_DIR / "uploads"


# ============================================================
# THREE-WAY MATCH CONFIGURATION
# ============================================================

PRICE_TOLERANCE_PERCENT = 5.0


# ============================================================
# APPLICATION SETTINGS
# ============================================================

class Settings(BaseSettings):

    # --------------------------------------------------------
    # Platform Service / Authentication
    # --------------------------------------------------------

    PLATFORM_AUTH_URL: str = "http://127.0.0.1:8005"

    # --------------------------------------------------------
    # Compliance Service
    # --------------------------------------------------------

    COMPLIANCE_SERVICE_URL: str = "http://127.0.0.1:8003"

    # --------------------------------------------------------
    # MinIO Object Storage
    # --------------------------------------------------------

    MINIO_ENDPOINT: str = "127.0.0.1:9000"
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET: str = "supplier-documents"
    MINIO_SECURE: bool = False
    MINIO_PRESIGNED_EXPIRY_SECONDS: int = 300

    # --------------------------------------------------------
    # Kafka - Existing Compliance Consumer (R14)
    # Keep these settings unchanged.
    # --------------------------------------------------------

    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_CONSUMER_GROUP: str = "supplier-portal-service"
    KAFKA_STATUS_CHANGED_TOPIC: str = (
        "compliance.supplier.status_changed"
    )
    KAFKA_DLQ_TOPIC: str = (
        "compliance.supplier.status_changed.dlq"
    )
    KAFKA_AUTO_OFFSET_RESET: str = "earliest"

    KAFKA_ENABLED: bool = True
    KAFKA_RETRY_BACKOFF_SECONDS: float = 1.0
    KAFKA_MAX_RETRIES: int = 5

    # --------------------------------------------------------
    # Durable Compliance State (R14)
    # --------------------------------------------------------

    COMPLIANCE_DB_PATH: str = "data/compliance_state.db"
    
    # PostgreSQL - required, read from .env (no default credentials)
    DATABASE_URL: str
    
    SUPPLIER_DB_SCHEMA: str = "supplier_portal"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# IMPORTANT: Do not add a trailing comma here.
settings = Settings()
