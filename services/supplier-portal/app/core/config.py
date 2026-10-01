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

    # Platform Service / Authentication Service
    PLATFORM_AUTH_URL: str = "http://127.0.0.1:8005"
    COMPLIANCE_SERVICE_URL: str = "http://127.0.0.1:8003"


    # MinIO Object Storage
    MINIO_ENDPOINT: str = "127.0.0.1:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "supplier-documents"
    MINIO_SECURE: bool = False
    MINIO_PRESIGNED_EXPIRY_SECONDS: int = 300


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()