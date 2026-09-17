import pandas as pd
import pytest

from src.accuracy_monitor import monitor_forecast_accuracy


def test_accuracy_monitor_returns_expected_metrics():
    df = pd.DataFrame({
        "date": pd.date_range(
            "2026-01-01",
            periods=6,
            freq="MS"
        ),
        "actual": [
            100000,
            110000,
            120000,
            130000,
            140000,
            150000,
        ],
        "predicted": [
            99000,
            112000,
            118000,
            125000,
            125000,
            120000,
        ],
    })

    result = monitor_forecast_accuracy(
        df,
        window=3,
        threshold=10.0,
    )

    assert "metrics" in result
    assert "mape" in result["metrics"]
    assert "rmse" in result["metrics"]

    assert "latest_rolling_mape" in result
    assert result["alert"]["status"] == "WARNING"
    assert "degradation" in result["alert"]["message"].lower()
    assert "monitoring_data" in result
def test_accuracy_monitor_rejects_zero_actual():
    df = pd.DataFrame({
        "date": pd.date_range(
            "2026-01-01",
            periods=3,
            freq="MS"
        ),
        "actual": [100, 0, 120],
        "predicted": [95, 10, 125],
    })

    with pytest.raises(
        ValueError,
        match="non-zero"
    ):
        monitor_forecast_accuracy(
            df,
            window=3,
            threshold=10.0
        )   
def test_accuracy_monitor_reports_healthy_within_threshold():
    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=6, freq="MS"),
        "actual":    [100000, 110000, 120000, 130000, 140000, 150000],
        "predicted": [100500, 109500, 120600, 129400, 140700, 149300],
    })

    result = monitor_forecast_accuracy(
        df,
        window=3,
        threshold=10.0,
    )

    assert result["alert"]["status"] == "HEALTHY"
    assert result["metrics"]["mape"] < 10.0         