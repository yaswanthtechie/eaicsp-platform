import hashlib
import hmac
import os

from fastapi import Header, HTTPException, status


SERVICE_API_KEYS = {
    "inventory": os.getenv("INVENTORY_SERVICE_API_KEY"),
    "compliance": os.getenv("COMPLIANCE_SERVICE_API_KEY"),
    "logistics": os.getenv("LOGISTICS_SERVICE_API_KEY"),
    "supplier_portal": os.getenv("SUPPLIER_PORTAL_SERVICE_API_KEY"),
    "api_gateway": os.getenv("API_GATEWAY_SERVICE_API_KEY"),
}

def verify_service_api_key(
    x_api_key: str | None = Header(default=None),
):
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing service API key",
        )

    for service_name, expected_key in SERVICE_API_KEYS.items():
        if expected_key and hmac.compare_digest(x_api_key, expected_key):
            return {
                "service": service_name,
                "auth_type": "api_key",
            }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid service API key",
    )