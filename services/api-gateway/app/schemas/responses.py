from pydantic import BaseModel, RootModel
from typing import Dict

class RootResponse(BaseModel):
    message: str
    status: str
    version: str

class HealthResponse(RootModel[Dict[str, str]]):
    pass
