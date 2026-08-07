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
    """
    Request schema for POST /detect
    """

    model: ModelName
    reading: SensorReading


class DetectWindowRequest(BaseModel):
    """
    Request schema for POST /detect-window

    Accepts the latest N sensor readings from the client.
    """

    model: ModelName
    readings: list[SensorReading]


__all__ = [
    "SensorReading",
    "PredictionRequest",
    "DetectWindowRequest",
    "ModelName",
]