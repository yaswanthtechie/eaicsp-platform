from pydantic_settings import BaseSettings
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
        "/api/v1/auth": "http://localhost:8000",
    }
    
    # Request Settings
    TIMEOUT_SECONDS: int = 5
    MAX_RETRIES: int = 3

    class Config:
        env_file = ".env"
        # In pydantic v2 we can also use model_config if needed, but Config works depending on version
        # model_config = {"env_file": ".env"}

settings = Settings()
