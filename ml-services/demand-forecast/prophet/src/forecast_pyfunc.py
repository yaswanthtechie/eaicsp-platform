"""
MLflow pyfunc for the R15 production demand forecast (issue #229).

Top-down: Prophet forecasts total daily demand across the seed, then each
SKU/warehouse pair gets its share of the last SHARE_WINDOW_DAYS of sales.
The 80% interval is the 10th/90th percentile of pooled pair-level backtest
errors (actual / predicted - 1), per horizon bucket.
"""

import json
from datetime import datetime, timedelta, timezone

import holidays
import mlflow
import pandas as pd
from prophet import Prophet
from prophet.serialize import model_from_json

from src.multi_horizon_config import HORIZON_BUCKETS, MAX_FORECAST_DAYS, PROPHET_PARAMS

_US_HOLIDAYS = holidays.US()


def _holiday_flags(dates) -> list[int]:
    # Same definition as multi_horizon_inference.create_daily_features.
    return [int(pd.Timestamp(d).date() in _US_HOLIDAYS) for d in dates]


def fit_prophet(daily: pd.DataFrame) -> Prophet:
    """daily: columns date, quantity_sold, one row per day."""
    model = Prophet(**PROPHET_PARAMS)
    model.add_regressor("is_holiday")
    model.fit(pd.DataFrame({
        "ds": daily["date"],
        "y": daily["quantity_sold"],
        "is_holiday": _holiday_flags(daily["date"]),
    }))
    return model


def aggregate_forecast(model, start, horizon: int) -> pd.DataFrame:
    """Total demand for `horizon` days from `start`: columns date, yhat (>= 0)."""
    dates = pd.date_range(start, periods=horizon, freq="D")
    future = pd.DataFrame({"ds": dates, "is_holiday": _holiday_flags(dates)})
    yhat = model.predict(future)["yhat"].clip(lower=0).to_numpy()
    return pd.DataFrame({"date": dates, "yhat": yhat})


def horizon_bucket(day: int) -> str:
    for low, high in HORIZON_BUCKETS:
        if low <= day <= high:
            return f"{low}-{high}"
    raise ValueError(f"Day {day} is outside 1-{MAX_FORECAST_DAYS}.")


def build_pair_forecast(aggregate: pd.DataFrame, share: float, intervals: dict, horizon: int) -> pd.DataFrame:
    """Scale the aggregate forecast to one pair and attach the 80% interval."""
    rows = []
    head = aggregate.iloc[:horizon]
    for day, (date, yhat) in enumerate(zip(head["date"], head["yhat"]), start=1):
        predicted = round(float(yhat) * share, 3)
        ratio = intervals[horizon_bucket(day)]
        lower = round(min(predicted, max(0.0, predicted * (1 + ratio["low"]))), 3)
        upper = round(max(predicted, predicted * (1 + ratio["high"])), 3)
        rows.append({
            "date": pd.Timestamp(date).date().isoformat(),
            "predicted": predicted,
            "lower_bound": lower,
            "upper_bound": upper,
        })
    return pd.DataFrame(rows)


class DemandForecastModel(mlflow.pyfunc.PythonModel):
    """Input: one row of sku_id, warehouse_id, horizon. Output: `horizon` daily rows from tomorrow (UTC)."""

    def load_context(self, context):
        with open(context.artifacts["prophet"], encoding="utf-8") as file:
            self.prophet = model_from_json(file.read())
        with open(context.artifacts["shares"], encoding="utf-8") as file:
            self.shares = json.load(file)
        with open(context.artifacts["intervals"], encoding="utf-8") as file:
            self.intervals = json.load(file)

    def predict(self, context, model_input: pd.DataFrame, params=None) -> pd.DataFrame:
        if len(model_input) != 1:
            raise ValueError("Send exactly one row: sku_id, warehouse_id, horizon.")

        row = model_input.iloc[0]
        sku_id, warehouse_id, horizon = str(row["sku_id"]), str(row["warehouse_id"]), int(row["horizon"])

        if not 1 <= horizon <= MAX_FORECAST_DAYS:
            raise ValueError(f"horizon must be between 1 and {MAX_FORECAST_DAYS}")
        key = f"{sku_id}|{warehouse_id}"
        if key not in self.shares:
            raise ValueError(f"Unknown SKU/warehouse pair: {sku_id} at {warehouse_id}")

        start = datetime.now(timezone.utc).date() + timedelta(days=1)
        aggregate = aggregate_forecast(self.prophet, start, horizon)
        return build_pair_forecast(aggregate, self.shares[key], self.intervals, horizon)