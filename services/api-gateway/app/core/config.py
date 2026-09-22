"""
Application configuration for the API Gateway.
"""

from pathlib import Path

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
    LOAD_TEST_MODE: bool = False

    # --------------------------------------------------
    # Downstream Service URLs
    # --------------------------------------------------

    PLATFORM_SERVICE_URL: str = "http://localhost:8005"
    INVENTORY_SERVICE_URL: str = "http://localhost:8001"
    SHIPMENTS_SERVICE_URL: str = "http://localhost:8002"
    COMPLIANCE_SERVICE_URL: str = "http://localhost:8003"
    PURCHASE_ORDERS_SERVICE_URL: str = "http://localhost:8004"
    SUPPLIER_RISK_SERVICE_URL: str = "http://localhost:8006"

    # Service-to-service authentication
    API_GATEWAY_SERVICE_API_KEY: str | None = None

    # --------------------------------------------------
    # Downstream Service Routes
    # --------------------------------------------------

    SERVICE_ROUTES: dict[str, str] = {
        "/api/v1/inventory": "http://localhost:8001",
        "/api/v1/shipments": "http://localhost:8002",
        "/api/v1/compliance": "http://localhost:8003",
        "/api/v1/purchase-orders": "http://localhost:8004",
        "/api/v1/auth": "http://localhost:8005",
        "/api/v1/supplier-risk": "http://localhost:8006",
    }

    # Explicit human-readable service name overrides (optional)
    SERVICE_NAMES: dict[str, str] = {
        "/api/v1/inventory": "Inventory Service",
        "/api/v1/shipments": "Shipments Service",
        "/api/v1/compliance": "Compliance Service",
        "/api/v1/purchase-orders": "Purchase Order Service",
        "/api/v1/auth": "Auth Service",
        "/api/v1/supplier-risk": "Supplier Risk Service",
    }

    # --------------------------------------------------
    # HTTP Client Configuration
    # --------------------------------------------------

    TIMEOUT_SECONDS: int = 5
    # MAX_RETRIES: number of retries to attempt on retryable failures (e.g. 2 → original + 2 retries)
    MAX_RETRIES: int = 2

    # --------------------------------------------------
    # JWT Configuration
    # --------------------------------------------------
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"

    # --------------------------------------------------
    # Rate Limiting Configuration
    # --------------------------------------------------
    TRUSTED_PROXIES: list[str] = []
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    ROLE_RATE_LIMITS: dict[str, int] = {
        "ceo": 200,
        "vp_operations": 200,
        "procurement_manager": 100,
        "logistics_manager": 100,
        "compliance_officer": 100,
        "warehouse_manager": 100,
        "analyst": 60,
        "supplier": 60,
        "default": 60,
    }

    def get_role_rate_limit(self, role: str | None = None) -> int:
        """
        Return the rate limit quota for a given role name.
        """
        if not role:
            return self.ROLE_RATE_LIMITS.get("default", 60)
        normalized = str(role).lower().strip().replace(" ", "_")
        return self.ROLE_RATE_LIMITS.get(
            normalized, self.ROLE_RATE_LIMITS.get("default", 60)
        )

    # --------------------------------------------------
    # Circuit Breaker Configuration
    # --------------------------------------------------
    CIRCUIT_BREAKER_FAILURE_RATE_THRESHOLD: float = 0.50
    CIRCUIT_BREAKER_WINDOW_SECONDS: int = 60
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: float = 30.0

    def model_post_init(self, __context: object = None, /) -> None:
        """
        Synchronize individual downstream URLs with the route mapping table.

        Configuration Precedence:
            1. Explicit environment configuration (SERVICE_ROUTES)
            2. Explicit individual service URL (*_SERVICE_URL)
            3. Default configuration

        Explicit SERVICE_ROUTES values are never silently overwritten by default
        service URLs.
        """
        routes_explicitly_set = "SERVICE_ROUTES" in self.model_fields_set
        self.SERVICE_ROUTES = dict(self.SERVICE_ROUTES)

        route_url_mappings = {
            "/api/v1/inventory": "INVENTORY_SERVICE_URL",
            "/api/v1/auth": "PLATFORM_SERVICE_URL",
            "/api/v1/shipments": "SHIPMENTS_SERVICE_URL",
            "/api/v1/compliance": "COMPLIANCE_SERVICE_URL",
            "/api/v1/purchase-orders": "PURCHASE_ORDERS_SERVICE_URL",
            "/api/v1/supplier-risk": "SUPPLIER_RISK_SERVICE_URL",
        }

        for prefix, url_attr in route_url_mappings.items():
            url_value = getattr(self, url_attr, None)
            if not url_value:
                continue

            if routes_explicitly_set:
                # Explicit SERVICE_ROUTES takes precedence over *_SERVICE_URL
                if prefix not in self.SERVICE_ROUTES:
                    self.SERVICE_ROUTES[prefix] = url_value
            else:
                # When SERVICE_ROUTES is not explicitly set, *_SERVICE_URL populates routes
                self.SERVICE_ROUTES[prefix] = url_value

    model_config = SettingsConfigDict(
        env_file=(
            Path(__file__).resolve().parent.parent.parent / ".env",
            ".env",
        ),
        extra="ignore",
    )


# Singleton settings instance
settings = Settings()