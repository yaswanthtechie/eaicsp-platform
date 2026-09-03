import pandas as pd
import numpy as np
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
)

from .preprocess import MODEL_FEATURES


TARGET_COLUMN = "delivery_days"

PURCHASE_TIMESTAMP_COLUMN = (
    "order_purchase_timestamp"
)

ESTIMATED_DELIVERY_COLUMN = (
    "order_estimated_delivery_date"
)


def _calculate_olist_estimate(
    test,
):
    """
    Calculate Olist's estimated delivery time in days.

    The estimate is calculated only from information that
    would be available at order purchase time:

        estimated delivery date
        -
        purchase timestamp

    This is used strictly as an evaluation baseline and is
    never passed to the XGBoost model.
    """

    required_columns = {
        PURCHASE_TIMESTAMP_COLUMN,
        ESTIMATED_DELIVERY_COLUMN,
    }

    missing_columns = (
        required_columns
        - set(test.columns)
    )

    if missing_columns:
        raise ValueError(
            "Test data is missing required Olist baseline "
            f"columns: {sorted(missing_columns)}"
        )

    purchase_timestamp = pd.to_datetime(
        test[
            PURCHASE_TIMESTAMP_COLUMN
        ],
        errors="coerce",
    )

    estimated_delivery = pd.to_datetime(
        test[
            ESTIMATED_DELIVERY_COLUMN
        ],
        errors="coerce",
    )

    if purchase_timestamp.isna().any():
        raise ValueError(
            "Test data contains missing or invalid "
            "order_purchase_timestamp values."
        )

    if estimated_delivery.isna().any():
        raise ValueError(
            "Test data contains missing or invalid "
            "order_estimated_delivery_date values."
        )

    estimated_days = (
        estimated_delivery
        - purchase_timestamp
    ).dt.total_seconds() / (
        24 * 60 * 60
    )

    if not np.isfinite(
        estimated_days.to_numpy()
    ).all():
        raise ValueError(
            "Olist estimated delivery baseline contains "
            "non-finite values."
        )

    if (
        estimated_days < 0
    ).any():
        raise ValueError(
            "Olist estimated delivery date occurs before "
            "the purchase timestamp."
        )

    return estimated_days.to_numpy(
        dtype=float
    )


def evaluate_model(
    model,
    train,
    test,
):
    """
    Evaluate XGBoost against two baselines.

    Baseline 1:
        Training-set median delivery time.

    Baseline 2:
        Olist's estimated delivery date converted into
        estimated delivery duration.

    Both baselines and XGBoost are evaluated on the same
    chronological test set.

    order_purchase_timestamp and
    order_estimated_delivery_date are evaluation metadata
    only and are never passed to the model.
    """

    # ---------------------------------------------------------
    # 1. Prepare test features
    # ---------------------------------------------------------
    X_test = test[
        MODEL_FEATURES
    ].copy()

    y_test = test[
        TARGET_COLUMN
    ]

    # ---------------------------------------------------------
    # 2. XGBoost predictions
    # ---------------------------------------------------------
    predictions = model.predict(
        X_test
    )

    predictions = np.asarray(
        predictions,
        dtype=float,
    )

    if not np.isfinite(
        predictions
    ).all():
        raise ValueError(
            "Model produced non-finite predictions."
        )

    # ---------------------------------------------------------
    # 3. XGBoost metrics
    # ---------------------------------------------------------
    mae = mean_absolute_error(
        y_test,
        predictions,
    )

    rmse = np.sqrt(
        mean_squared_error(
            y_test,
            predictions,
        )
    )

    # ---------------------------------------------------------
    # 4. Honest naive baseline
    #
    # Use ONLY the training median.
    # ---------------------------------------------------------
    baseline_prediction = float(
        train[
            TARGET_COLUMN
        ].median()
    )

    baseline_predictions = np.full(
        shape=len(y_test),
        fill_value=baseline_prediction,
        dtype=float,
    )

    baseline_mae = mean_absolute_error(
        y_test,
        baseline_predictions,
    )

    baseline_rmse = np.sqrt(
        mean_squared_error(
            y_test,
            baseline_predictions,
        )
    )

    # ---------------------------------------------------------
    # 5. Olist estimated-delivery baseline
    #
    # This uses:
    #
    #     estimated_delivery_date
    #     -
    #     purchase_timestamp
    #
    # It is evaluated on exactly the same test rows.
    # ---------------------------------------------------------
    olist_predictions = (
        _calculate_olist_estimate(
            test
        )
    )

    olist_mae = mean_absolute_error(
        y_test,
        olist_predictions,
    )

    olist_rmse = np.sqrt(
        mean_squared_error(
            y_test,
            olist_predictions,
        )
    )

    # ---------------------------------------------------------
    # 6. XGBoost improvement over training median
    # ---------------------------------------------------------
    mae_improvement = (
        (
            baseline_mae
            - mae
        )
        / baseline_mae
        * 100
    )

    rmse_improvement = (
        (
            baseline_rmse
            - rmse
        )
        / baseline_rmse
        * 100
    )

    # ---------------------------------------------------------
    # 7. XGBoost improvement over Olist estimate
    # ---------------------------------------------------------
    olist_mae_improvement = (
        (
            olist_mae
            - mae
        )
        / olist_mae
        * 100
    )

    olist_rmse_improvement = (
        (
            olist_rmse
            - rmse
        )
        / olist_rmse
        * 100
    )

    # ---------------------------------------------------------
    # 8. Report
    # ---------------------------------------------------------
    print("\nETA Evaluation")
    print("==============")

    print(
        f"\nTrain rows : {len(train)}"
    )

    print(
        f"Test rows  : {len(test)}"
    )

    # ---------------------------------------------------------
    # XGBoost
    # ---------------------------------------------------------
    print("\nModel:")
    print("  XGBoost Regressor")

    print("\nXGBoost test metrics:")

    print(
        f"  MAE  : {mae:.4f} days"
    )

    print(
        f"  RMSE : {rmse:.4f} days"
    )

    # ---------------------------------------------------------
    # Training median baseline
    # ---------------------------------------------------------
    print("\nNaive baseline:")
    print(
        f"  Training median delivery_days: "
        f"{baseline_prediction:.4f}"
    )

    print("\nNaive baseline metrics:")

    print(
        f"  MAE  : {baseline_mae:.4f} days"
    )

    print(
        f"  RMSE : {baseline_rmse:.4f} days"
    )

    # ---------------------------------------------------------
    # Olist baseline
    # ---------------------------------------------------------
    print("\nOlist estimated-delivery baseline:")
    print(
        "  Estimated duration = "
        "order_estimated_delivery_date "
        "- order_purchase_timestamp"
    )

    print("\nOlist baseline metrics:")

    print(
        f"  MAE  : {olist_mae:.4f} days"
    )

    print(
        f"  RMSE : {olist_rmse:.4f} days"
    )

    # ---------------------------------------------------------
    # Improvement over training median
    # ---------------------------------------------------------
    print(
        "\nXGBoost improvement over "
        "training-median baseline:"
    )

    print(
        f"  MAE  : {mae_improvement:.2f}%"
    )

    print(
        f"  RMSE : {rmse_improvement:.2f}%"
    )

    # ---------------------------------------------------------
    # Improvement over Olist estimate
    # ---------------------------------------------------------
    print(
        "\nXGBoost improvement over "
        "Olist estimated-delivery baseline:"
    )

    print(
        f"  MAE  : {olist_mae_improvement:.2f}%"
    )

    print(
        f"  RMSE : {olist_rmse_improvement:.2f}%"
    )

    # ---------------------------------------------------------
    # 9. Return all evaluation metrics
    # ---------------------------------------------------------
    return {
        # XGBoost
        "mae": mae,
        "rmse": rmse,

        # Training-median baseline
        "baseline_prediction": (
            baseline_prediction
        ),
        "baseline_mae": baseline_mae,
        "baseline_rmse": baseline_rmse,

        # Olist baseline
        "olist_baseline_mae": (
            olist_mae
        ),
        "olist_baseline_rmse": (
            olist_rmse
        ),

        # Improvement over training median
        "mae_improvement": (
            mae_improvement
        ),
        "rmse_improvement": (
            rmse_improvement
        ),

        # Improvement over Olist estimate
        "olist_mae_improvement": (
            olist_mae_improvement
        ),
        "olist_rmse_improvement": (
            olist_rmse_improvement
        ),
    }