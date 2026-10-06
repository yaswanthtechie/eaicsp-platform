import math

import pytest
import pandas as pd

from src.intermittent_demand import (
    calculate_adi,
    calculate_cv2,
    classify_demand,
)
from src.intermittent_demand import (
    calculate_adi,
    calculate_cv2,
    classify_demand,
    classify_sku_demand,
)

from src.intermittent_demand import (
    calculate_adi,
    calculate_cv2,
    classify_demand,
    classify_demand_with_metrics,
    classify_sku_demand,
    croston_forecast,
    mase,
    split_sku_history,
    evaluate_croston_vs_naive,
    evaluate_intermittent_skus,
    route_intermittent_skus,
    run_intermittent_demand_pipeline,
)


def test_adi_for_continuous_demand():
    demand = [100, 110, 105, 115]

    assert calculate_adi(demand) == 1.0


def test_adi_for_intermittent_demand():
    demand = [0, 0, 50, 0, 0, 70, 0, 0, 60, 0, 0, 80]

    assert calculate_adi(demand) == 3.0


def test_adi_for_all_zero_demand():
    demand = [0, 0, 0, 0]

    assert math.isinf(calculate_adi(demand))


def test_cv2_for_stable_demand():
    demand = [100, 100, 100, 100]

    assert calculate_cv2(demand) == 0.0


def test_cv2_ignores_zero_periods():
    demand_with_zeros = [0, 100, 0, 100, 0, 100]
    demand_without_zeros = [100, 100, 100]

    assert calculate_cv2(demand_with_zeros) == pytest.approx(
        calculate_cv2(demand_without_zeros)
    )


def test_smooth_classification():
    demand = [100, 105, 110, 108, 112, 115]

    assert classify_demand(demand) == "smooth"


def test_intermittent_classification():
    demand = [0, 0, 50, 0, 0, 70, 0, 0, 60, 0, 0, 80]

    assert classify_demand(demand) == "intermittent"


def test_erratic_classification():
    demand = [20, 300, 15, 280, 10, 350, 12, 400, 8, 320, 15, 380]

    assert classify_demand(demand) == "erratic"


def test_lumpy_classification():
    demand = [0, 0, 0, 20, 0, 0, 0, 250, 0, 0, 0, 300]

    assert classify_demand(demand) == "lumpy"


def test_negative_demand_is_rejected():
    with pytest.raises(ValueError):
        calculate_adi([10, -5, 20])


def test_empty_history_is_rejected():
    with pytest.raises(ValueError):
        calculate_adi([])


def test_nan_is_rejected():
    with pytest.raises(ValueError):
        calculate_cv2([10, float("nan"), 20])
def test_classify_sku_demand_from_dataframe():
    import pandas as pd

    df = pd.DataFrame(
        {
            "sku_id": [
                "SKU001",
                "SKU001",
                "SKU002",
                "SKU002",
                "SKU002",
                "SKU002",
            ],
            "quantity_sold": [
                100,
                110,
                0,
                50,
                0,
                70,
            ],
        }
    )

    result = classify_sku_demand(df)

    assert len(result) == 2

    sku001 = next(x for x in result if x["sku_id"] == "SKU001")
    sku002 = next(x for x in result if x["sku_id"] == "SKU002")

    assert sku001["classification"] == "smooth"
    assert sku001["adi"] == 1.0

    assert sku002["classification"] == "intermittent"
    assert sku002["adi"] == pytest.approx(2.0)        
def test_croston_returns_requested_horizon():
    demand = [0, 0, 50, 0, 0, 70, 0, 0, 60, 0, 0, 80]

    forecast = croston_forecast(
        demand,
        horizon=3,
    )

    assert len(forecast) == 3


def test_croston_forecast_is_non_negative():
    demand = [0, 0, 50, 0, 0, 70, 0, 0, 60, 0, 0, 80]

    forecast = croston_forecast(
        demand,
        horizon=3,
    )

    assert all(value >= 0 for value in forecast)


def test_croston_all_zero_demand():
    demand = [0, 0, 0, 0]

    forecast = croston_forecast(
        demand,
        horizon=3,
    )

    assert forecast == [0.0, 0.0, 0.0]


def test_croston_constant_intermittent_demand():
    demand = [0, 0, 50, 0, 0, 50, 0, 0, 50]

    forecast = croston_forecast(
        demand,
        horizon=2,
    )

    assert len(forecast) == 2
    assert forecast[0] == pytest.approx(50 / 3)
    assert forecast[1] == pytest.approx(50 / 3)


def test_croston_rejects_negative_demand():
    with pytest.raises(ValueError):
        croston_forecast([0, -10, 20], horizon=2)


def test_croston_rejects_invalid_horizon():
    with pytest.raises(ValueError):
        croston_forecast([0, 10, 0], horizon=0)


def test_croston_rejects_invalid_alpha():
    with pytest.raises(ValueError):
        croston_forecast([0, 10, 0], horizon=2, alpha=0)

    with pytest.raises(ValueError):
        croston_forecast([0, 10, 0], horizon=2, alpha=1.5)
        
def test_mase_uses_training_scale():
    # training naive errors: |20-0|, |0-20|, |20-0| -> scale 20
    # MAE = (0 + 20 + 20) / 3 = 13.33 -> MASE = 2/3
    result = mase([0, 0, 80], [0, 20, 60], train=[0, 20, 0, 20])

    assert result == pytest.approx(2 / 3)


def test_mase_perfect_forecast():
    assert mase([0, 50, 0, 70], [0, 50, 0, 70], train=[0, 10]) == pytest.approx(0.0)


def test_mase_rejects_length_mismatch():
    with pytest.raises(ValueError):
        mase([0, 10, 20], [0, 10], train=[0, 10])


def test_mase_rejects_empty_values():
    with pytest.raises(ValueError):
        mase([], [], train=[0, 10])


def test_mase_rejects_negative_actual():
    with pytest.raises(ValueError):
        mase([0, -10, 20], [0, 10, 20], train=[0, 10])


def test_mase_rejects_negative_forecast():
    with pytest.raises(ValueError):
        mase([0, 10, 20], [0, -10, 20], train=[0, 10])


def test_mase_rejects_short_training_history():
    with pytest.raises(ValueError):
        mase([10], [10], train=[5])


def test_mase_rejects_constant_training_history():
    with pytest.raises(ValueError):
        mase([10, 10, 10], [10, 10, 10], train=[10, 10, 10])


def test_all_zero_test_window_does_not_crash():
    # This exact input crashed before the fix.
    result = evaluate_croston_vs_naive(
        [0, 0, 5, 0, 0, 3, 0, 0, 4],
        [0, 0, 0],
    )

    assert result["croston_mase"] > 0
    assert result["naive_mase"] > 0
def test_split_sku_history_uses_chronological_order():
    sku_df = pd.DataFrame(
        {
            "date": [
                "2025-03-01",
                "2025-01-01",
                "2025-02-01",
                "2025-04-01",
            ],
            "sku_id": ["SKU001"] * 4,
            "quantity_sold": [30, 10, 20, 40],
        }
    )

    train, test = split_sku_history(
        sku_df,
        test_periods=1,
    )

    assert train["date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2025-01-01",
        "2025-02-01",
        "2025-03-01",
    ]

    assert test["date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2025-04-01",
    ]


def test_split_sku_history_default_test_periods():
    sku_df = pd.DataFrame(
        {
            "date": pd.date_range(
                "2025-01-01",
                periods=12,
                freq="MS",
            ),
            "sku_id": ["SKU001"] * 12,
            "quantity_sold": range(12),
        }
    )

    train, test = split_sku_history(sku_df)

    assert len(train) == 9
    assert len(test) == 3


def test_split_sku_history_rejects_empty_history():
    sku_df = pd.DataFrame(
        columns=["date", "sku_id", "quantity_sold"]
    )

    with pytest.raises(ValueError):
        split_sku_history(sku_df)


def test_split_sku_history_rejects_invalid_test_periods():
    sku_df = pd.DataFrame(
        {
            "date": ["2025-01-01", "2025-02-01"],
            "sku_id": ["SKU001", "SKU001"],
            "quantity_sold": [10, 20],
        }
    )

    with pytest.raises(ValueError):
        split_sku_history(sku_df, test_periods=0)  

def test_evaluate_croston_vs_naive_returns_mase():
    train = [0, 0, 50, 0, 0, 70, 0, 0, 60]
    test = [0, 0, 80]

    result = evaluate_croston_vs_naive(
        train,
        test,
    )

    assert "croston_mase" in result
    assert "naive_mase" in result
    assert "croston_forecast" in result
    assert "naive_forecast" in result

    assert len(result["croston_forecast"]) == 3
    assert len(result["naive_forecast"]) == 3


def test_evaluate_croston_vs_naive_uses_test_length_as_horizon():
    train = [0, 0, 50, 0, 0, 70]
    test = [0, 0, 60, 0]

    result = evaluate_croston_vs_naive(
        train,
        test,
    )

    assert len(result["croston_forecast"]) == 4
    assert len(result["naive_forecast"]) == 4


def test_evaluate_croston_vs_naive_rejects_mismatched_horizon():
    train = [0, 0, 50, 0, 0, 70]
    test = [0, 0, 60]

    with pytest.raises(ValueError):
        evaluate_croston_vs_naive(
            train,
            test,
            horizon=2,
        )


def test_evaluate_croston_vs_naive_rejects_empty_train():
    with pytest.raises(ValueError):
        evaluate_croston_vs_naive(
            [],
            [0, 10],
        )


def test_evaluate_croston_vs_naive_rejects_empty_test():
    with pytest.raises(ValueError):
        evaluate_croston_vs_naive(
            [0, 10],
            [],
        )
def test_evaluate_intermittent_skus():
    df = pd.DataFrame(
        {
            "date": pd.date_range(
                "2025-01-01",
                periods=12,
                freq="MS",
            ).tolist() * 2,
            "sku_id": (
                ["SKU002"] * 12
                + ["SKU001"] * 12
            ),
            "quantity_sold": [
                0, 0, 50, 0, 0, 70,
                0, 0, 60, 0, 0, 80,
                100, 105, 110, 108, 112, 115,
                118, 120, 122, 125, 128, 130,
            ],
        }
    )

    results = evaluate_intermittent_skus(
        df,
        test_periods=3,
    )

    assert len(results) == 1
    assert results[0]["sku_id"] == "SKU002"
    assert results[0]["classification"] == "intermittent"
    assert "croston_mase" in results[0]
    assert "naive_mase" in results[0]        
def test_route_intermittent_skus_selects_croston():
    results = [
        {
            "sku_id": "SKU002",
            "classification": "intermittent",
            "adi": 3.0,
            "cv2": 0.04,
            "croston_mase": 0.81,
            "naive_mase": 1.16,
        }
    ]

    routed = route_intermittent_skus(results)

    assert routed[0]["selected_model"] == "croston"


def test_route_intermittent_skus_selects_naive():
    results = [
        {
            "sku_id": "SKU004",
            "classification": "lumpy",
            "adi": 4.0,
            "cv2": 0.62,
            "croston_mase": 0.69,
            "naive_mase": 0.67,
        }
    ]

    routed = route_intermittent_skus(results)

    assert routed[0]["selected_model"] == "naive"


def test_route_intermittent_skus_tie_selects_croston():
    results = [
        {
            "sku_id": "SKU002",
            "classification": "intermittent",
            "adi": 3.0,
            "cv2": 0.04,
            "croston_mase": 0.8,
            "naive_mase": 0.8,
        }
    ]

    routed = route_intermittent_skus(results)

    assert routed[0]["selected_model"] == "croston" 
def test_run_intermittent_demand_pipeline():
    sku002_values = [
        0, 0, 50, 0, 0, 70,
        0, 0, 60, 0, 0, 80,
        0, 0, 90,
    ]

    sku004_values = [
        0, 10, 0, 300, 0, 0,
        350, 0, 20, 0, 0, 250,
        0, 0, 300,
    ]

    dates = pd.date_range(
        "2025-01-01",
        periods=15,
        freq="MS",
    )

    df = pd.DataFrame(
        {
            "date": dates.tolist() * 2,
            "sku_id": (
                ["SKU002"] * 15
                + ["SKU004"] * 15
            ),
            "quantity_sold": (
                sku002_values
                + sku004_values
            ),
        }
    )

    results = run_intermittent_demand_pipeline(
        df,
        test_periods=3,
    )

    assert len(results) == 2

    result_by_sku = {
        result["sku_id"]: result
        for result in results
    }

    assert (
        result_by_sku["SKU002"]["classification"]
        == "intermittent"
    )

    assert result_by_sku["SKU002"]["selected_model"] in {
        "croston",
        "naive",
    }

    assert (
        result_by_sku["SKU004"]["classification"]
        == "lumpy"
    )

    assert result_by_sku["SKU004"]["selected_model"] in {
        "croston",
        "naive",
    }

    assert (
        "selected_test_mase"
        in result_by_sku["SKU002"]
    )

    assert (
        "selected_test_mase"
        in result_by_sku["SKU004"]
    )
def _sku_frame(values, sku_id="SKU_X"):
    return pd.DataFrame(
        {
            "date": pd.date_range(
                "2024-01-01",
                periods=len(values),
                freq="MS",
            ),
            "sku_id": sku_id,
            "quantity_sold": values,
        }
    )


def test_routing_does_not_depend_on_test_window():
    # 6 train | 3 validation | 3 test
    history = [0, 0, 40, 0, 0, 55, 0, 0, 50]

    a = run_intermittent_demand_pipeline(
        _sku_frame(history + [0, 0, 60])
    )

    b = run_intermittent_demand_pipeline(
        _sku_frame(history + [500, 500, 500])
    )

    assert len(a) == 1
    assert len(b) == 1

    assert a[0]["selected_model"] == b[0]["selected_model"]

    assert (
        a[0]["selected_test_mase"]
        != b[0]["selected_test_mase"]
    )                                     