<<<<<<< HEAD
from pydantic import BaseModel, RootModel
from typing import Dict

class RootResponse(BaseModel):
=======
"""
Response models used by the API Gateway.
"""

from typing import Dict

from pydantic import BaseModel, RootModel


class RootResponse(BaseModel):
    """
    Root endpoint response model.
    """

>>>>>>> mahendher/round3-api-gateway
    message: str
    status: str
    version: str

<<<<<<< HEAD
class HealthResponse(RootModel[Dict[str, str]]):
    pass
=======

class HealthResponse(RootModel[Dict[str, str]]):
    """
    Health status of downstream services.

    Example:
    {
        "inventory": "UP",
        "auth": "UP",
        "supplier-risk": "DOWN"
    }
    """

    pass
>>>>>>> mahendher/round3-api-gateway
