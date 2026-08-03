import os
import pickle
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


MODEL_PATH = "models/xgb_model.pkl"

DATE_COLUMN = "ds"
TARGET_COLUMN = "y"



def create_features(df):

    df = df.copy()

    df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN])

    df = df.sort_values(DATE_COLUMN)


    df["lag_1"] = df[TARGET_COLUMN].shift(1)

    df["lag_7"] = df[TARGET_COLUMN].shift(7)

    df["lag_30"] = df[TARGET_COLUMN].shift(30)



    df["rolling_mean_7"] = (
        df[TARGET_COLUMN]
        .shift(1)
        .rolling(7)
        .mean()
    )


    df["rolling_mean_30"] = (
        df[TARGET_COLUMN]
        .shift(1)
        .rolling(30)
        .mean()
    )


    df["rolling_std_7"] = (
        df[TARGET_COLUMN]
        .shift(1)
        .rolling(7)
        .std()
    )
    # ----------------------
    # Holiday Feature
    # ----------------------

    df["is_holiday"] = (
        (
            df[DATE_COLUMN].dt.month.isin([11,12])
        )
        |
        (
            df[DATE_COLUMN].dt.day.isin([1,25])
        )
    ).astype(int)


    df["day_of_week"] = df[DATE_COLUMN].dt.dayofweek

    df["month"] = df[DATE_COLUMN].dt.month

    df["quarter"] = df[DATE_COLUMN].dt.quarter

    df["year"] = df[DATE_COLUMN].dt.year


    df = df.dropna()

    return df



FEATURES = [

    "lag_1",
    "lag_7",
    "lag_30",

    "rolling_mean_7",
    "rolling_mean_30",

    "rolling_std_7",
    "is_holiday",

    "day_of_week",

    "month",
    "quarter",
    "year"

]



def train_xgboost(df):


    print("\n========== Preparing XGBoost ==========")


    print(
        "Original Rows:",
        len(df)
    )


    df = create_features(df)


    print(
        "Feature Rows:",
        len(df)
    )



    # SAME TEST PERIOD AS PROPHET

    test_start_date = pd.Timestamp("2015-01-01")


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



    X_train = train[FEATURES]

    y_train = train[TARGET_COLUMN]


    X_test = test[FEATURES]

    y_test = test[TARGET_COLUMN]




    model = XGBRegressor(

        n_estimators=300,

        learning_rate=0.03,

        max_depth=5,

        subsample=0.8,

        colsample_bytree=0.8,

        objective="reg:squarederror",

        random_state=42

    )



    print(
        "\n========== Training XGBoost =========="
    )



    # IMPORTANT:
    # Do NOT start another MLflow run here

    model.fit(
        X_train,
        y_train
    )


    predictions = model.predict(
        X_test
    )
    # ----------------------
    # Prediction Interval
    # ----------------------

    residuals = y_test.values - predictions

    residual_std = np.std(residuals)

    print(
        "Residual Std:",
        residual_std
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



    print("MAE:", mae)

    print("RMSE:", rmse)

    print("R2:", r2)



    # Log into existing MLflow run

    if mlflow.active_run():

        mlflow.log_params({

            "xgb_n_estimators":300,

            "xgb_learning_rate":0.03,

            "xgb_max_depth":5

        })


        mlflow.log_metrics({

            "xgb_mae":mae,

            "xgb_rmse":rmse,

            "xgb_r2":r2

        })


        mlflow.xgboost.log_model(
            model,
            "xgb_model"
        )



    os.makedirs(
        "models",
        exist_ok=True
    )


    with open(
        MODEL_PATH,
        "wb"
    ) as f:


        pickle.dump(

            {
                "model":model,

                "features":FEATURES

            },

            f

        )


    print(
        "XGBoost saved:",
        MODEL_PATH
    )


    return {
    "model": model,
    "residual_std": residual_std,
    "features": FEATURES
}





def predict_xgboost(model_info, df):


    model = model_info["model"]

    residual_std = model_info["residual_std"]


    # create features using full history
    feature_df = create_features(df)


    X = feature_df[FEATURES]


    predictions = model.predict(X)


    interval = 1.96 * residual_std


    result = feature_df.copy()


    result["prediction"] = predictions

    result["lower"] = (
        predictions - interval
    )

    result["upper"] = (
        predictions + interval
    )


    return (
        predictions,
        result
    )




if __name__ == "__main__":

    print(
        "Run from main.py"
    )