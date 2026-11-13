import numpy as np
import pandas as pd
import pytest

import src.sales_anomaly as sa
from src.calibrate_sales_anomaly import calibrate
from src.sales_anomaly_eval import CLEAN_SEED, make_data


def test_calibration_returns_a_threshold_and_leaves_z_spike_alone():

    before = sa.Z_SPIKE
    clean, _ = make_data(CLEAN_SEED, with_events=False)

    drop_rate, z_spike = calibrate(clean)

    assert 0 <= drop_rate < 2 / 1000
    assert np.isfinite(z_spike) and z_spike > 0
    assert sa.Z_SPIKE == before


def test_calibration_fails_clearly_when_drops_exceed_budget():

    dates = pd.date_range("2026-01-05", periods=120, freq="D")
    qty = np.full(120, 50.0)
    qty[70::3] = 0.0  # frequent drops to zero
    data = pd.DataFrame(
        {"sale_date": dates, "sku_id": "SKU-000001", "warehouse": "WH-BLR-01", "quantity_sold": qty}
    )

    with pytest.raises(ValueError, match="over the budget"):
        calibrate(data)