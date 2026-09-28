from datetime import date, datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class ForecastPoint(BaseModel):
    """
    One forecast period, in the shape the demand-forecast
    service already returns:

        {"date": "2026-10-01", "predicted": 125.5,
         "lower": 98.2, "upper": 151.9}

    `date` is the first day of the forecast month.
    """

    # Tolerant reader: the forecast service may add fields
    # later without breaking Inventory.
    model_config = ConfigDict(
        extra="ignore"
    )

    date: date

    predicted: float = Field(
        ...,
        ge=0,
    )

    lower: float = Field(
        ...,
        ge=0,
    )

    upper: float = Field(
        ...,
        ge=0,
    )

    @model_validator(mode="after")
    def check_point(self):
        if self.date.day != 1:
            raise ValueError(
                "Monthly forecast dates must be the first "
                "day of the month"
            )

        if not (self.lower <= self.predicted <= self.upper):
            raise ValueError(
                "Forecast point must satisfy "
                "lower <= predicted <= upper"
            )

        return self


class ForecastContract(BaseModel):
    """
    Contract v1 for demand forecasts that Inventory will
    consume. Contract-first only: Inventory does not call
    the Forecast Service yet.

    Matches the forecast service's existing response
    (`forecast`, `model_version`) and adds the fields
    Inventory needs to use it safely (see README section 9,
    "Contract gaps to agree with the Forecast owner").
    """

    # Tolerant reader: extra response fields such as
    # latency_ms are ignored rather than rejected.
    model_config = ConfigDict(
        extra="ignore"
    )

    contract_version: Literal["v1"]

    sku_id: str = Field(
        ...,
        min_length=1,
    )

    warehouse_id: str = Field(
        ...,
        min_length=1,
    )

    granularity: Literal["monthly"]

    # Coverage of the lower/upper band, e.g. 0.8 for an
    # 80% prediction interval. Needed to turn the band
    # into a standard deviation for safety stock.
    interval_level: float = Field(
        ...,
        gt=0,
        lt=1,
    )

    model_version: str = Field(
        ...,
        min_length=1,
    )

    generated_at: datetime

    forecast: list[ForecastPoint] = Field(
        ...,
        min_length=1,
    )

    @model_validator(mode="after")
    def check_forecast_order(self):
        dates = [point.date for point in self.forecast]

        if dates != sorted(set(dates)):
            raise ValueError(
                "Forecast dates must be unique and in "
                "ascending order"
            )

        return self