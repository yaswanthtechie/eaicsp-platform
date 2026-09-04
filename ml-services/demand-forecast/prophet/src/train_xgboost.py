import os
import pickle
from pathlib import Path
import numpy as np
import pandas as pd

from xgboost import XGBRegressor

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)

import mlflow
import mlflow.xgboost

from src.inference import (
    create_features,
    predict_xgboost,
    predict_future_xgboost,
    FEATURES,
    DATE_COLUMN,
    TARGET_COLUMN,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent

MODEL_PATH = PROJECT_ROOT / "models" / "xgb_model.pkl"


XGB_PARAMS = {

    "n_estimators": 300,

    "learning_rate": 0.03,

    "max_depth": 5,

    "subsample": 0.8,

    "colsample_bytree": 0.8,

    "objective": "reg:squarederror",

    "random_state": 42
}


def train_xgboost(df):

    print(
        "\n========== Preparing XGBoost =========="
    )

    print(
        "Original Rows:",
        len(df)
    )

    # Create features
    df = create_features(
        df,
        drop_missing=True
    )

    print(
        "Feature Rows:",
        len(df)
    )

    # Same split as Prophet
    test_start_date = pd.Timestamp(
        "2015-01-01"
    )

    train = df[
        df[DATE_COLUMN] < test_start_date
    ].copy()

    test = df[
        df[DATE_COLUMN] >= test_start_date
    ].copy()

    print(
        "XGB Train Rows:",
        len(train)
    )

    print(
        "XGB Test Rows:",
        len(test)
    )

    # Training data
    X_train = train[FEATURES]

    y_train = train[TARGET_COLUMN]

    # Testing data
    X_test = test[FEATURES]

    y_test = test[TARGET_COLUMN]

    # Create XGBoost model
    model = XGBRegressor(
        **XGB_PARAMS
    )

    print(
        "\n========== Training XGBoost =========="
    )

    # Train model
    model.fit(
        X_train,
        y_train
    )

    # =====================================
    # TRAIN RESIDUAL STD
    # Used for prediction intervals
    # =====================================

    train_predictions = model.predict(
        X_train
    )

    train_residuals = (
        y_train.values
        -
        train_predictions
    )

    residual_std = np.std(
        train_residuals
    )

    print(
        "Training Residual Std:",
        residual_std
    )

    # =====================================
    # TEST EVALUATION ONLY
    # =====================================

    predictions = model.predict(
        X_test
    )

    mae = mean_absolute_error(
        y_test,
        predictions
    )

    rmse = np.sqrt(
        mean_squared_error(
            y_test,
            predictions
        )
    )

    r2 = r2_score(
        y_test,
        predictions
    )

    print(
        "MAE:",
        mae
    )

    print(
        "RMSE:",
        rmse
    )

    print(
        "R2:",
        r2
    )

    # =====================================
    # MLflow Logging
    # =====================================

    if mlflow.active_run():

        mlflow.log_params(
            XGB_PARAMS
        )

        mlflow.log_metrics({

            "xgb_mae": mae,

            "xgb_rmse": rmse,

            "xgb_r2": r2,

            "xgb_residual_std": residual_std

        })

        mlflow.xgboost.log_model(
            model,
            "xgb_model"
        )

    # =====================================
    # Save XGBoost Package
    # =====================================

        os.makedirs(
        MODEL_PATH.parent,
        exist_ok=True
    )

    xgb_package = {

        "model": model,

        "features": FEATURES,

        "residual_std": residual_std

    }

    with open(
        MODEL_PATH,
        "wb"
    ) as f:

        pickle.dump(
            xgb_package,
            f
        )

    print(
        "XGBoost saved:",
        MODEL_PATH
    )

    return xgb_package