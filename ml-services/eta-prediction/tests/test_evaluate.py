import numpy as np
import pytest

from src.evaluate import evaluate_model


class DummyModel:
    """Simple deterministic model for evaluation tests."""

    def predict(self, X):
        return np.array(
            [
                5.0,
                10.0,
                15.0,
                20.0,
            ]
        )


def test_evaluation_model_and_baselines(
    sample_model_data,
):
    """
    Test XGBoost evaluation against both the training-median
    baseline and Olist's estimated-delivery baseline.

    All data comes from the shared sample_model_data fixture
    in conftest.py.
    """

    train = sample_model_data["train"]
    test = sample_model_data["test"]

    model = DummyModel()

    results = evaluate_model(
        model,
        train,
        test,
    )

    # ---------------------------------------------------------
    # 1. Model metrics must exist and be finite
    # ---------------------------------------------------------
    assert np.isfinite(
        results["mae"]
    )

    assert np.isfinite(
        results["rmse"]
    )

    # ---------------------------------------------------------
    # 2. Training-median baseline
    # ---------------------------------------------------------
    expected_baseline = train[
        "delivery_days"
    ].median()

    assert (
        results["baseline_prediction"]
        == expected_baseline
    )

    assert np.isfinite(
        results["baseline_mae"]
    )

    assert np.isfinite(
        results["baseline_rmse"]
    )

    # ---------------------------------------------------------
    # 3. Olist baseline
    # ---------------------------------------------------------
    assert np.isfinite(
        results["olist_baseline_mae"]
    )

    assert np.isfinite(
        results["olist_baseline_rmse"]
    )

    # ---------------------------------------------------------
    # 4. Olist baseline must be evaluated against
    #    the same test target.
    # ---------------------------------------------------------
    expected_olist_predictions = (
        (
            test[
                "order_estimated_delivery_date"
            ]
            - test[
                "order_purchase_timestamp"
            ]
        )
        .dt.total_seconds()
        / (24 * 60 * 60)
    ).to_numpy(
        dtype=float
    )

    expected_actual = test[
        "delivery_days"
    ].to_numpy(
        dtype=float
    )

    expected_olist_mae = np.mean(
        np.abs(
            expected_actual
            - expected_olist_predictions
        )
    )

    expected_olist_rmse = np.sqrt(
        np.mean(
            (
                expected_actual
                - expected_olist_predictions
            )
            ** 2
        )
    )

    assert np.isclose(
        results["olist_baseline_mae"],
        expected_olist_mae,
    )

    assert np.isclose(
        results["olist_baseline_rmse"],
        expected_olist_rmse,
    )

    # ---------------------------------------------------------
    # 5. Improvement metrics must exist
    # ---------------------------------------------------------
    assert np.isfinite(
        results["mae_improvement"]
    )

    assert np.isfinite(
        results["rmse_improvement"]
    )

    assert np.isfinite(
        results["olist_mae_improvement"]
    )

    assert np.isfinite(
        results["olist_rmse_improvement"]
    )


def test_evaluation_returns_expected_metrics(
    sample_model_data,
):
    """
    Verify evaluate_model() returns the complete evaluation
    result contract.
    """

    train = sample_model_data["train"]
    test = sample_model_data["test"]

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
        "olist_baseline_mae",
        "olist_baseline_rmse",
        "mae_improvement",
        "rmse_improvement",
        "olist_mae_improvement",
        "olist_rmse_improvement",
    }

    assert set(
        results.keys()
    ) == expected_keys


def test_baseline_uses_training_data_only(
    sample_model_data,
):
    """
    Verify the naive median baseline is calculated exclusively
    from the training target and does not use test targets.
    """

    train = sample_model_data["train"].copy()
    test = sample_model_data["test"].copy()

    original_training_median = train[
        "delivery_days"
    ].median()

    # Make test target completely different.
    test[
        "delivery_days"
    ] = [
        1000.0,
        2000.0,
        3000.0,
        4000.0,
    ]

    results = evaluate_model(
        DummyModel(),
        train,
        test,
    )

    assert (
        results["baseline_prediction"]
        == original_training_median
    )


def test_olist_baseline_uses_estimated_and_purchase_dates(
    sample_model_data,
):
    """
    Verify Olist's baseline uses only:

        order_estimated_delivery_date
        -
        order_purchase_timestamp

    and does not depend on the training target.
    """

    train = sample_model_data["train"].copy()
    test = sample_model_data["test"].copy()

    results = evaluate_model(
        DummyModel(),
        train,
        test,
    )

    expected_predictions = (
        (
            test[
                "order_estimated_delivery_date"
            ]
            - test[
                "order_purchase_timestamp"
            ]
        )
        .dt.total_seconds()
        / (24 * 60 * 60)
    ).to_numpy(
        dtype=float
    )

    actual = test[
        "delivery_days"
    ].to_numpy(
        dtype=float
    )

    expected_mae = np.mean(
        np.abs(
            actual
            - expected_predictions
        )
    )

    expected_rmse = np.sqrt(
        np.mean(
            (
                actual
                - expected_predictions
            )
            ** 2
        )
    )

    assert np.isclose(
        results["olist_baseline_mae"],
        expected_mae,
    )

    assert np.isclose(
        results["olist_baseline_rmse"],
        expected_rmse,
    )


def test_olist_baseline_is_independent_of_training_target(
    sample_model_data,
):
    """
    Changing training delivery_days must not change the Olist
    estimated-delivery baseline metrics.
    """

    train = sample_model_data["train"].copy()
    test = sample_model_data["test"].copy()

    first_results = evaluate_model(
        DummyModel(),
        train,
        test,
    )

    # Change only the training target.
    train[
        "delivery_days"
    ] = (
        train[
            "delivery_days"
        ]
        + 1000.0
    )

    second_results = evaluate_model(
        DummyModel(),
        train,
        test,
    )

    assert np.isclose(
        first_results[
            "olist_baseline_mae"
        ],
        second_results[
            "olist_baseline_mae"
        ],
    )

    assert np.isclose(
        first_results[
            "olist_baseline_rmse"
        ],
        second_results[
            "olist_baseline_rmse"
        ],
    )


def test_evaluation_does_not_pass_baseline_columns_to_model(
    sample_model_data,
):
    """
    Verify order_purchase_timestamp and
    order_estimated_delivery_date are evaluation metadata,
    not model features.
    """

    train = sample_model_data["train"]
    test = sample_model_data["test"]

    class InspectingModel:
        def __init__(self):
            self.received_columns = None

        def predict(self, X):
            self.received_columns = list(
                X.columns
            )

            return np.zeros(
                len(X),
                dtype=float,
            )

    model = InspectingModel()

    evaluate_model(
        model,
        train,
        test,
    )

    assert (
        "order_purchase_timestamp"
        not in model.received_columns
    )

    assert (
        "order_estimated_delivery_date"
        not in model.received_columns
    )