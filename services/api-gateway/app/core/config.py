# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict

class Settings(BaseSettings):
    APP_NAME: str = "API Gateway"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Gateway Routes
    SERVICE_ROUTES: Dict[str, str] = {
        "/api/v1/inventory": "http://localhost:8001",
        "/api/v1/shipments": "http://localhost:8002",
        "/api/v1/compliance": "http://localhost:8003",
        "/api/v1/purchase-orders": "http://localhost:8004",
        "/api/v1/auth": "http://localhost:8005",
        "/api/v1/supplier-risk": "http://localhost:8006",
        "/timeout": "http://localhost:8001",
        "/error": "http://localhost:8001",
    }
    
    # Request Settings
    TIMEOUT_SECONDS: int = 5
    MAX_RETRIES: int = 2

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

settings = Settings()
