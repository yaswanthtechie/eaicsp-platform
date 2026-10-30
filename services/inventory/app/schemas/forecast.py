from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ForecastPoint(BaseModel):
    """One daily forecast point returned by the A2 Forecast Service."""

    model_config = ConfigDict(extra="ignore")

    date: date
    predicted: float = Field(..., ge=0)
    lower_bound: float = Field(..., ge=0)
    upper_bound: float = Field(..., ge=0)

    @model_validator(mode="after")
    def check_point(self):
        if not (
            self.lower_bound
            <= self.predicted
            <= self.upper_bound
        ):
            raise ValueError(
                "Forecast point must satisfy "
                "lower_bound <= predicted <= upper_bound"
            )
        return self


class ForecastContract(BaseModel):
    """Daily demand forecast contract consumed by Inventory."""

    model_config = ConfigDict(extra="ignore")

    contract_version: Literal["v1"]
    sku_id: str = Field(..., min_length=1)
    warehouse_id: str = Field(..., min_length=1)
    granularity: Literal["daily"]
    horizon: int = Field(..., ge=1, le=90)
    interval_level: float = Field(..., gt=0, lt=1)
    model_version: str = Field(..., min_length=1)
    generated_at: datetime
    forecast: list[ForecastPoint] = Field(..., min_length=1)

    @model_validator(mode="after")
    def check_forecast_order(self):
        dates = [point.date for point in self.forecast]

        if dates != sorted(set(dates)):
            raise ValueError(
                "Forecast dates must be unique and in ascending order"
            )

        return self
