"""
Response models used by the API Gateway.
"""

from pydantic import BaseModel, RootModel


class RootResponse(BaseModel):
    """
    Root endpoint response model.
    """

    message: str
    status: str
    version: str


class HealthResponse(RootModel[dict[str, str]]):
    """
    Health status of downstream services.

    Example:
    {
        "inventory": "UP",
        "auth": "UP",
        "supplier-risk": "DOWN"
    }
    """