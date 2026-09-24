from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ForecastContract(BaseModel):
    """
    Contract for forecast data that Inventory will consume
    in the future.

    This is contract-only.
    Inventory does not call the Forecast Service yet.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    contract_version: Literal["v1"] = "v1"

    sku_id: str = Field(
        ...,
        min_length=1,
    )

    warehouse_id: str = Field(
        ...,
        min_length=1,
    )

    forecast_date: date

    forecast_quantity: float = Field(
        ...,
        ge=0,
    )

    horizon_days: int = Field(
        ...,
        gt=0,
    )

    generated_at: datetime

    confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )