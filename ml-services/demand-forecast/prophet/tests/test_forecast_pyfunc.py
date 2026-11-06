from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from src.forecast_pyfunc import DemandForecastModel, build_pair_forecast, horizon_bucket
from src.production_model import ProductionForecastModel
from src.seed_demand import load_seed_sales, pair_shares

INTERVALS = {
    "1-1": {"low": -0.2, "high": 0.2},
    "2-7": {"low": -0.3, "high": 0.3},
    "8-30": {"low": -0.4, "high": 0.5},
    "31-90": {"low": -1.5, "high": 0.8},   # low < -1 must clamp to 0
}


class _FlatProphet:
    def predict(self, future):
        return pd.DataFrame({"yhat": [1000.0] * len(future)})


def _model():
    model = DemandForecastModel()
    model.prophet = _FlatProphet()
    model.shares = {"SKU-000123|WH-BLR-01": 0.01}
    model.intervals = INTERVALS
    return model


def _aggregate(days):
    dates = pd.date_range("2026-11-03", periods=days, freq="D")
    return pd.DataFrame({"date": dates, "yhat": [1000.0] * days})


def test_horizon_buckets():
    assert horizon_bucket(1) == "1-1"
    assert horizon_bucket(7) == "2-7"
    assert horizon_bucket(90) == "31-90"
    with pytest.raises(ValueError):
        horizon_bucket(91)


def test_pair_forecast_shape_and_bounds():
    out = build_pair_forecast(_aggregate(90), 0.01, INTERVALS, 90)
    assert len(out) == 90
    assert (out["predicted"] == 10.0).all()
    assert (out["lower_bound"] >= 0).all()
    assert (out["lower_bound"] <= out["predicted"]).all()
    assert (out["predicted"] <= out["upper_bound"]).all()
    assert out.iloc[-1]["lower_bound"] == 0.0


def test_predict_starts_tomorrow_with_exact_horizon():
    out = _model().predict(None, pd.DataFrame([{"sku_id": "SKU-000123", "warehouse_id": "WH-BLR-01", "horizon": 7}]))
    assert len(out) == 7
    assert out.iloc[0]["date"] == (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()

def test_predict_rejects_unknown_pair_and_bad_horizon():
    model = _model()
    with pytest.raises(ValueError, match="Unknown"):
        model.predict(None, pd.DataFrame([{"sku_id": "SKU-999999", "warehouse_id": "WH-BLR-01", "horizon": 3}]))
    with pytest.raises(ValueError, match="horizon"):
        model.predict(None, pd.DataFrame([{"sku_id": "SKU-000123", "warehouse_id": "WH-BLR-01", "horizon": 91}]))


def test_output_passes_serving_contract_validation():
    """Same checks forecast-service runs on the registered model (production_model.py)."""
    pyfunc = _model()

    class _Loaded:
        def predict(self, model_input):
            return pyfunc.predict(None, model_input)

    serving = ProductionForecastModel()
    serving.model, serving.model_version = _Loaded(), "1"
    points = serving.predict("SKU-000123", "WH-BLR-01", 30)
    assert len(points) == 30


def test_seed_loader_rejects_non_canonical_ids(tmp_path):
    path = tmp_path / "sales_daily.csv"
    path.write_text("date,sku_id,warehouse_id,quantity_sold,unit_price\n2026-10-12,P-1,WH-BLR-01,3,10.0\n")
    with pytest.raises(ValueError, match="Non-canonical"):
        load_seed_sales(path)


def test_pair_shares_sum_to_one():
    sales = pd.DataFrame({
        "date": pd.to_datetime(["2026-10-13", "2026-10-13", "2026-10-14"]),
        "sku_id": ["SKU-000001", "SKU-000002", "SKU-000001"],
        "warehouse_id": ["WH-BLR-01"] * 3,
        "quantity_sold": [2, 6, 2],
    })
    shares = pair_shares(sales)
    assert shares == {"SKU-000001|WH-BLR-01": 0.4, "SKU-000002|WH-BLR-01": 0.6}