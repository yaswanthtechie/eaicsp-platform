from enum import Enum

from pydantic import BaseModel


class SensorReading(BaseModel):
    """
    Schema for a single sensor reading.

    reading_id uniquely identifies the reading/event.
    It is used to identify the same reading when it appears
    in multiple overlapping windows.
    """

    reading_id: int
    temperature: float
    humidity: float
    stock_count: int


class ModelName(str, Enum):
    """
    Supported anomaly detection models.
    """

    iforest = "iforest"
    lof = "lof"
    ocsvm = "ocsvm"


class PredictionRequest(BaseModel):
    """
    Request schema for POST /detect.
    """

    model: ModelName
    reading: SensorReading


class DetectWindowRequest(BaseModel):
    """
    Request schema for POST /detect-window.

    Accepts the latest N sensor readings from the client.
    Each reading contains a unique reading_id so that
    repeated detections across overlapping windows can
    be identified and deduplicated.
    """

    model: ModelName
    readings: list[SensorReading]


__all__ = [
    "SensorReading",
    "PredictionRequest",
    "DetectWindowRequest",
    "ModelName",
]
