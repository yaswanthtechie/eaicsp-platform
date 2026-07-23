from enum import Enum

from pydantic import BaseModel


class SensorReading(BaseModel):
    temperature: float
    humidity: float
    stock_count: int


class ModelName(str, Enum):
    iforest = "iforest"
    lof = "lof"
    ocsvm = "ocsvm"


class PredictionRequest(BaseModel):
    model: ModelName
    reading: SensorReading


__all__ = [
    "SensorReading",
    "PredictionRequest",
    "ModelName",
]
