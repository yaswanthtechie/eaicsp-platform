"""Daily sales per SKU x warehouse, and opening stock.

Demand model (all vectorised, shape = days x SKUs x warehouses):

    lambda = class_base * sku_scale * warehouse_weight * weekday * month * trend * noise
    quantity_sold ~ Poisson(lambda)

Class A/B/C set the base rate, so slow C-class items produce zero-sales days
(about 14% of rows overall). October and November carry a festive uplift.
Rows are emitted in (date, sku_id, warehouse_id) order.
"""

import numpy as np
import pandas as pd

_CLASS_BASE = {"A": 18.0, "B": 6.0, "C": 2.0}
_WEEKDAY = np.array([1.05, 1.05, 1.00, 1.00, 1.10, 0.95, 0.85])  # Mon..Sun
_MONTH = np.array([0.95, 0.95, 1.00, 1.00, 1.00, 0.95, 0.95, 1.00, 1.05, 1.30, 1.40, 1.10])
_PROMO_RATE = 0.03
_PROMO_DISCOUNT = 0.90
_ANNUAL_PRICE_DRIFT = 0.04


def date_index(end_date: str, days: int) -> pd.DatetimeIndex:
    return pd.date_range(end=end_date, periods=days, freq="D")


def base_rate(skus: pd.DataFrame, wh: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
    """Mean daily demand per (sku, warehouse), before time effects. Shape (S, W)."""
    class_rate = skus["abc_class"].map(_CLASS_BASE).to_numpy()
    sku_scale = rng.lognormal(0.0, 0.25, size=len(skus))
    return (class_rate * sku_scale)[:, None] * wh["demand_weight"].to_numpy()[None, :]


def sales(skus: pd.DataFrame, wh: pd.DataFrame, base: np.ndarray, dates: pd.DatetimeIndex,
          rng: np.random.Generator) -> pd.DataFrame:
    D, S, W = len(dates), len(skus), len(wh)

    time_factor = (
        _WEEKDAY[dates.dayofweek.to_numpy()]
        * _MONTH[dates.month.to_numpy() - 1]
        * (1.0 + 0.10 * np.arange(D) / max(D - 1, 1))  # +10% growth over the window
    )
    lam = time_factor[:, None, None] * base[None, :, :]
    lam *= rng.gamma(shape=8.0, scale=1 / 8.0, size=(D, S, W))  # over-dispersion
    qty = rng.poisson(lam).astype("int32")

    list_price = skus["unit_price"].to_numpy()[None, :, None]
    drift = (1.0 + _ANNUAL_PRICE_DRIFT * np.arange(D) / 365.0)[:, None, None]
    promo = np.where(rng.random((D, S, W)) < _PROMO_RATE, _PROMO_DISCOUNT, 1.0)
    price = np.round(list_price * drift * promo, 2)

    date_str = np.datetime_as_string(dates.to_numpy().astype("datetime64[D]"), unit="D")
    return pd.DataFrame({
        "date": np.repeat(date_str, S * W),
        "sku_id": np.tile(np.repeat(skus["sku_id"].to_numpy(), W), D),
        "warehouse_id": np.tile(wh["warehouse_id"].to_numpy(), D * S),
        "quantity_sold": qty.reshape(-1),
        "unit_price": price.reshape(-1),
    })


def opening_stock(skus: pd.DataFrame, wh: pd.DataFrame, base: np.ndarray,
                  first_date: pd.Timestamp, rng: np.random.Generator) -> pd.DataFrame:
    """On-hand at the start of the first sales day: 10-45 days of cover, ~2% stocked out."""
    S, W = len(skus), len(wh)
    cover_days = rng.uniform(10, 45, size=(S, W))
    qty = np.ceil(base * cover_days).astype("int32")
    qty[rng.random((S, W)) < 0.02] = 0
    return pd.DataFrame({
        "snapshot_date": first_date.strftime("%Y-%m-%d"),
        "sku_id": np.repeat(skus["sku_id"].to_numpy(), W),
        "warehouse_id": np.tile(wh["warehouse_id"].to_numpy(), S),
        "quantity_on_hand": qty.reshape(-1),
    })

def current_stock(skus: pd.DataFrame, wh: pd.DataFrame, base: np.ndarray,
                  snapshot_date: pd.Timestamp,
                  rng: np.random.Generator) -> pd.DataFrame:
    """Current on-hand stock at the end of the sales window:
    10-45 days of cover, with approximately 2% of SKU-warehouse pairs stocked out.
    """
    S, W = len(skus), len(wh)
    cover_days = rng.uniform(10, 45, size=(S, W))
    qty = np.ceil(base * cover_days).astype("int32")
    qty[rng.random((S, W)) < 0.02] = 0
    return pd.DataFrame({
        "snapshot_date": snapshot_date.strftime("%Y-%m-%d"),
        "sku_id": np.repeat(skus["sku_id"].to_numpy(), W),
        "warehouse_id": np.tile(wh["warehouse_id"].to_numpy(), S),
        "quantity_on_hand": qty.reshape(-1),
    })
