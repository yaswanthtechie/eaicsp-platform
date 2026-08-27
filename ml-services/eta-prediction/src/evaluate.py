import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error

from .preprocess import MODEL_FEATURES


TARGET_COLUMN = "delivery_days"


def evaluate_model(model, train, test):
    """Evaluate XGBoost against the honest naive baseline."""

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
    # 3. Honest naive baseline
    #
    # Use ONLY the training median.
    # ---------------------------------------------------------
    baseline_prediction = train[
        TARGET_COLUMN
    ].median()

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
    # 4. Improvement over baseline
    # ---------------------------------------------------------
    mae_improvement = (
        (baseline_mae - mae)
        / baseline_mae
        * 100
    )

    rmse_improvement = (
        (baseline_rmse - rmse)
        / baseline_rmse
        * 100
    )

    # ---------------------------------------------------------
    # 5. Report
    # ---------------------------------------------------------
    print("\nETA Evaluation")
    print("==============")

    print(
        f"\nTrain rows : {len(train)}"
    )

    print(
        f"Test rows  : {len(test)}"
    )

    print("\nModel:")
    print("  XGBoost Regressor")

    print("\nXGBoost test metrics:")
    print(
        f"  MAE  : {mae:.4f} days"
    )

    print(
        f"  RMSE : {rmse:.4f} days"
    )

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

    print("\nImprovement over baseline:")
    print(
        f"  MAE  : {mae_improvement:.2f}%"
    )

    print(
        f"  RMSE : {rmse_improvement:.2f}%"
    )

    return {
        "mae": mae,
        "rmse": rmse,
        "baseline_prediction": baseline_prediction,
        "baseline_mae": baseline_mae,
        "baseline_rmse": baseline_rmse,
        "mae_improvement": mae_improvement,
        "rmse_improvement": rmse_improvement,
    }