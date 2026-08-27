import numpy as np
import pandas as pd

from src.evaluate import evaluate_model


class DummyModel:
    """Simple deterministic model for evaluation testing."""

    def predict(self, X):
        return np.array(
            [5.0, 10.0, 15.0]
        )


def make_train_data():
    return pd.DataFrame(
        {
            "order_id": [
                "order_1",
                "order_2",
                "order_3",
            ],
            "delivery_days": [
                5.0,
                10.0,
                15.0,
            ],
            "order_purchase_timestamp": pd.to_datetime(
                [
                    "2018-01-01",
                    "2018-01-02",
                    "2018-01-03",
                ]
            ),
        }
    )


def make_test_data():
    return pd.DataFrame(
        {
            "order_id": [
                "order_4",
                "order_5",
                "order_6",
            ],
            "delivery_days": [
                6.0,
                12.0,
                18.0,
            ],
            "order_purchase_timestamp": pd.to_datetime(
                [
                    "2018-01-04",
                    "2018-01-05",
                    "2018-01-06",
                ]
            ),
            "purchase_year": [
                2018,
                2018,
                2018,
            ],
            "purchase_month": [
                1,
                1,
                1,
            ],
            "purchase_day_of_week": [
                3,
                4,
                5,
            ],
            "purchase_hour": [
                10,
                11,
                12,
            ],
            "origin_lat": [
                -23.55,
                -22.90,
                -19.92,
            ],
            "origin_lng": [
                -46.63,
                -43.18,
                -43.94,
            ],
            "destination_lat": [
                -23.56,
                -22.91,
                -19.93,
            ],
            "destination_lng": [
                -46.65,
                -43.20,
                -43.95,
            ],
            "distance_km": [
                5.0,
                10.0,
                15.0,
            ],
            "item_count": [
                1,
                2,
                3,
            ],
            "total_weight_kg": [
                0.5,
                1.0,
                1.5,
            ],
            "total_volume_cm3": [
                100.0,
                200.0,
                300.0,
            ],
            "total_freight_value": [
                5.0,
                10.0,
                15.0,
            ],
            "product_category_name": [
                "electronics",
                "books",
                "toys",
            ],
        }
    )


def test_evaluation_model_and_naive_baseline():
    """Test model evaluation against the training-median baseline."""

    train = make_train_data()
    test = make_test_data()

    model = DummyModel()

    results = evaluate_model(
        model,
        train,
        test,
    )

    # ---------------------------------------------------------
    # Training median must be used as the baseline.
    # ---------------------------------------------------------
    expected_baseline = 10.0

    assert (
        results["baseline_prediction"]
        == expected_baseline
    )

    # ---------------------------------------------------------
    # Model metrics
    #
    # Predictions: 5, 10, 15
    # Actual:      6, 12, 18
    #
    # Absolute errors: 1, 2, 3
    # MAE = 2
    # ---------------------------------------------------------
    assert results["mae"] == 2.0

    expected_rmse = np.sqrt(
        (
            1**2
            + 2**2
            + 3**2
        )
        / 3
    )

    assert np.isclose(
        results["rmse"],
        expected_rmse,
    )

    # ---------------------------------------------------------
    # Baseline metrics
    #
    # Baseline predicts 10 for every test order.
    # Actual: 6, 12, 18
    # Errors: 4, 2, 8
    # MAE = 14 / 3
    # ---------------------------------------------------------
    expected_baseline_mae = 14 / 3

    assert np.isclose(
        results["baseline_mae"],
        expected_baseline_mae,
    )

    expected_baseline_rmse = np.sqrt(
        (
            4**2
            + 2**2
            + 8**2
        )
        / 3
    )

    assert np.isclose(
        results["baseline_rmse"],
        expected_baseline_rmse,
    )

    # ---------------------------------------------------------
    # Model should beat this baseline.
    # ---------------------------------------------------------
    assert (
        results["mae"]
        < results["baseline_mae"]
    )

    assert (
        results["rmse"]
        < results["baseline_rmse"]
    )

    # ---------------------------------------------------------
    # Improvement should be positive.
    # ---------------------------------------------------------
    assert (
        results["mae_improvement"] > 0
    )

    assert (
        results["rmse_improvement"] > 0
    )


def test_evaluation_returns_expected_metrics():
    """Verify evaluation returns the complete result contract."""

    train = make_train_data()
    test = make_test_data()

    results = evaluate_model(
        DummyModel(),
        train,
        test,
    )

    expected_keys = {
        "mae",
        "rmse",
        "baseline_prediction",
        "baseline_mae",
        "baseline_rmse",
        "mae_improvement",
        "rmse_improvement",
    }

    assert set(results.keys()) == expected_keys


def test_baseline_uses_training_data_only():
    """Verify the naive baseline is calculated from training median."""

    train = make_train_data()
    test = make_test_data()

    # Make test target very different from training.
    test["delivery_days"] = [
        100.0,
        200.0,
        300.0,
    ]

    results = evaluate_model(
        DummyModel(),
        train,
        test,
    )

    # Must remain the training median = 10.
    assert (
        results["baseline_prediction"]
        == train["delivery_days"].median()
    )