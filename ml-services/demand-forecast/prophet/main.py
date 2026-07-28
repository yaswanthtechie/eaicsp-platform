from data import load_sales_data
from train_prophet import train_prophet, predict_prophet
from train_xgboost import train_xgboost, predict_xgboost
from evaluate import evaluate
from predict import predict
from ensemble import weighted_ensemble
from plot import save_forecast_plot

from mlflow_utils import (
    start_experiment,
    start_run,
    log_params,
    log_metrics,
    log_model,
    end_run
)


def main():

    # -----------------------------------
    # Load Data
    # -----------------------------------
    df = load_sales_data()

    print("Total Rows :", len(df))

    # -----------------------------------
    # Rename Columns for Prophet/XGBoost
    # -----------------------------------
    prophet_df = df.rename(
        columns={
            "date": "ds",
            "quantity_sold": "y"
        }
    )

    # -----------------------------------
    # Time-based Train/Test Split
    # -----------------------------------
    train_df = prophet_df[prophet_df["ds"] < "2015-01-01"].copy()
    test_df = prophet_df[prophet_df["ds"] >= "2015-01-01"].copy()

    print("Training Rows :", len(train_df))
    print("Testing Rows :", len(test_df))

    # -----------------------------------
    # Start MLflow
    # -----------------------------------
    start_experiment("Forecasting Project")
    start_run("Prophet_XGBoost_Ensemble")

    # -----------------------------------
    # Train Prophet
    # -----------------------------------
    print("\n========== Training Prophet ==========")

    prophet_model = train_prophet(train_df)

    print(" Prophet model trained successfully.")

    # -----------------------------------
    # Train XGBoost
    # -----------------------------------
    print("\n========== Training XGBoost ==========")

    xgb_model = train_xgboost(train_df)

    print(" XGBoost model trained successfully.")

    # -----------------------------------
    # Log Parameters
    # -----------------------------------
    log_params({
        "prophet_yearly": True,
        "xgb_estimators": 100,
        "xgb_learning_rate": 0.1,
        "ensemble_weights": "0.4_0.6"
    })

    # -----------------------------------
    # Predictions
    # -----------------------------------
    print("\n========== Predictions ==========")

    prophet_predictions = predict_prophet(
        prophet_model,
        test_df
    )

    xgb_predictions = predict_xgboost(
        xgb_model,
        test_df
    )

    # -----------------------------------
    # Prophet Evaluation
    # -----------------------------------
    print("\n========== Prophet Evaluation ==========")

    prophet_metrics = evaluate(
        test_df["y"].values,
        prophet_predictions
    )

    print(prophet_metrics)

    log_metrics({
        "prophet_mape": prophet_metrics["MAPE"],
        "prophet_rmse": prophet_metrics["RMSE"]
    })

    log_model(
        prophet_model,
        "Prophet_Model"
    )

    # -----------------------------------
    # XGBoost Evaluation
    # -----------------------------------
    print("\n========== XGBoost Evaluation ==========")

    xgb_metrics = evaluate(
        test_df["y"].values,
        xgb_predictions
    )

    print(xgb_metrics)

    log_metrics({
        "xgb_mape": xgb_metrics["MAPE"],
        "xgb_rmse": xgb_metrics["RMSE"]
    })

    log_model(
        xgb_model,
        "XGBoost_Model"
    )

    # -----------------------------------
    # Ensemble Evaluation
    # -----------------------------------
    print("\n========== Ensemble Evaluation ==========")

    ensemble_predictions = weighted_ensemble(
        prophet_predictions,
        xgb_predictions,
        prophet_weight=0.4,
        xgb_weight=0.6
    )

    ensemble_metrics = evaluate(
        test_df["y"].values,
        ensemble_predictions
    )

    print(ensemble_metrics)

    log_metrics({
        "ensemble_mape": ensemble_metrics["MAPE"],
        "ensemble_rmse": ensemble_metrics["RMSE"]
    })

    # -----------------------------------
    # Forecast Plot
    # -----------------------------------
    prophet_forecast = prophet_model.predict(test_df[["ds"]])

    save_forecast_plot(
        test_df,
        prophet_forecast
    )

    # -----------------------------------
    # Future Forecast
    # -----------------------------------
    print("\n========== Future Forecast ==========")

    result = predict(6)

    print("\nNext 6 Months Forecast:\n")

    for item in result["forecast"]:
        print(item)

    # -----------------------------------
    # End MLflow Run
    # -----------------------------------
    end_run()


if __name__ == "__main__":
    main()