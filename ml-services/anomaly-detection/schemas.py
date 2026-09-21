from enum import Enum

from pydantic import BaseModel, model_validator


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


class DetectAdaptiveRequest(BaseModel):
    """
    Request schema for POST /detect-adaptive.

    Accepts either one sensor reading or multiple sensor
    readings.

    A single reading preserves compatibility with the
    original adaptive API contract.

    Multiple readings are processed sequentially through
    the same stateful AdaptiveEngine.
    """

    model: ModelName
    reading: SensorReading | None = None
    readings: list[SensorReading] | None = None

    @model_validator(mode="after")
    def validate_reading_input(self):
        """
        Require exactly one adaptive input mode.

        The API accepts either:

            reading
                OR
            readings

        but not neither and not both.
        """

        if (
            self.reading is None
            and self.readings is None
        ):

            raise ValueError(
                "Either 'reading' or "
                "'readings' must be provided."
            )

        if (
            self.reading is not None
            and self.readings is not None
        ):

            raise ValueError(
                "Provide either 'reading' "
                "or 'readings', not both."
            )

        return self


__all__ = [
    "SensorReading",
    "ModelName",
    "PredictionRequest",
    "DetectWindowRequest",
    "DetectAdaptiveRequest",
]