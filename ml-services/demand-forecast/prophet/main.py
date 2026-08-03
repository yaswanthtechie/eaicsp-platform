import pandas as pd
import mlflow

from data import load_sales_data
from train_prophet import train_prophet, predict_prophet
from train_xgboost import train_xgboost, predict_xgboost
from evaluate import evaluate
from predict import predict

from ensemble import (
    weighted_ensemble,
    ensemble_interval
)

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

    # =====================================================
    # Load Dataset
    # =====================================================

    df = load_sales_data()

    print("=" * 60)
    print("Demand Forecasting Pipeline Started")
    print("=" * 60)

    print(f"Total Rows : {len(df)}")

    # =====================================================
    # Rename Columns
    # =====================================================

    prophet_df = df.rename(
        columns={
            "date": "ds",
            "quantity_sold": "y"
        }
    )

    prophet_df["ds"] = pd.to_datetime(
        prophet_df["ds"]
    )

    # =====================================================
    # Time Based Train/Test Split
    # =====================================================

    train_df = prophet_df[
        prophet_df["ds"] < "2015-01-01"
    ].copy()

    test_df = prophet_df[
        prophet_df["ds"] >= "2015-01-01"
    ].copy()

    print(f"Training Rows : {len(train_df)}")
    print(f"Testing Rows  : {len(test_df)}")

    # =====================================================
    # MLflow Experiment
    # =====================================================

    start_experiment(
        "Forecasting Project"
    )

    # Main MLflow run
    start_run(
        "Demand_Forecasting"
    )

    # =====================================================
    # Common Parameters
    # =====================================================

    common_params = {

        "train_rows": len(train_df),

        "test_rows": len(test_df),

        "prophet_yearly": True,

        "xgb_estimators": 300,

        "xgb_learning_rate": 0.03,

        "xgb_max_depth": 5

    }

    log_params(common_params)
        # =====================================================
    # Train Prophet
    # =====================================================

    print("\n========== Training Prophet ==========")

    prophet_model = train_prophet(
        train_df
    )

    print("Prophet model trained successfully.")

    # =====================================================
    # Train XGBoost
    # =====================================================

    print("\n========== Training XGBoost ==========")

    # Train on full history because lag features
    # require previous observations.
    xgb_result = train_xgboost(
        prophet_df
    )

    xgb_model = xgb_result["model"]

    print("XGBoost model trained successfully.")

    # =====================================================
    # Log Models
    # =====================================================

    log_model(
        prophet_model,
        "Prophet_Model"
    )

    log_model(
        xgb_model,
        "XGBoost_Model"
    )

    # =====================================================
    # Predictions
    # =====================================================

    print("\n========== Predictions ==========")

    prophet_forecast = predict_prophet(
        prophet_model,
        test_df
    )

    xgb_predictions, xgb_forecast = predict_xgboost(
        xgb_result,
        prophet_df
    )

    # Keep only the Prophet test period
    xgb_forecast = xgb_forecast[
        xgb_forecast["ds"] >= test_df["ds"].min()
    ].copy()

    # Align both models
    prophet_forecast = prophet_forecast.tail(
        len(xgb_forecast)
    )

    actual = xgb_forecast["y"].values

    print(
        "Prophet Test Predictions :",
        len(prophet_forecast)
    )

    print(
        "XGBoost Test Predictions :",
        len(xgb_forecast)
    )

    print(
        "Evaluation Samples :",
        len(actual)
    )
        # =====================================================
    # Prophet Evaluation
    # =====================================================

    print("\n========== Prophet Evaluation ==========")

    prophet_metrics = evaluate(
        actual,
        prophet_forecast["yhat"].values
    )

    print(prophet_metrics)

    # =====================================================
    # XGBoost Evaluation
    # =====================================================

    print("\n========== XGBoost Evaluation ==========")

    xgb_metrics = evaluate(
        actual,
        xgb_forecast["prediction"].values
    )

    print(xgb_metrics)

    # =====================================================
    # Common Parameters
    # =====================================================

    common_params = {

        "train_rows": len(train_df),

        "test_rows": len(test_df),

        "prophet_yearly": True,

        "xgb_estimators": 300,

        "xgb_learning_rate": 0.03,

        "xgb_max_depth": 5

    }
    # =====================================================
    # Ensemble Evaluation
    # =====================================================

    print("\n========== Ensemble Evaluation ==========")

    ensemble_results = []

    weight_combinations = [
        (0.5, 0.5),
        (0.4, 0.6),
        (0.3, 0.7)
    ]

    for prophet_weight, xgb_weight in weight_combinations:

        run_name = (
            f"Ensemble_"
            f"{int(prophet_weight * 100)}_"
            f"{int(xgb_weight * 100)}"
        )

        with mlflow.start_run(run_name=run_name, nested=True):

            log_params(common_params)

            log_params({
                "prophet_weight": prophet_weight,
                "xgb_weight": xgb_weight
            })

            ensemble_prediction = weighted_ensemble(
                prophet_forecast["yhat"].values,
                xgb_forecast["prediction"].values,
                prophet_weight=prophet_weight,
                xgb_weight=xgb_weight
            )

            ensemble_metrics = evaluate(
                actual,
                ensemble_prediction
            )

            print(f"\nWeights {prophet_weight}/{xgb_weight}")
            print(ensemble_metrics)

            log_metrics({
                "prophet_mape": prophet_metrics["MAPE"],
                "prophet_rmse": prophet_metrics["RMSE"],
                "xgb_mape": xgb_metrics["MAPE"],
                "xgb_rmse": xgb_metrics["RMSE"],
                "ensemble_mape": ensemble_metrics["MAPE"],
                "ensemble_rmse": ensemble_metrics["RMSE"]
            })

            log_model(
                prophet_model,
                "Prophet_Model"
            )

            log_model(
                xgb_model,
                "XGBoost_Model"
            )

            ensemble_lower, ensemble_upper = ensemble_interval(
                prophet_forecast["yhat_lower"].values,
                prophet_forecast["yhat_upper"].values,
                xgb_forecast["lower"].values,
                xgb_forecast["upper"].values,
                prophet_weight=prophet_weight,
                xgb_weight=xgb_weight
            )

            ensemble_results.append({
                "weights": f"{prophet_weight}-{xgb_weight}",
                "MAPE": ensemble_metrics["MAPE"],
                "RMSE": ensemble_metrics["RMSE"],
                "prediction": ensemble_prediction,
                "lower": ensemble_lower,
                "upper": ensemble_upper
            })

        
            # =====================================================
    # Best Ensemble
    # =====================================================

    best_model = min(
        ensemble_results,
        key=lambda x: x["RMSE"]
    )

    print("\n" + "=" * 60)
    print("BEST ENSEMBLE")
    print("=" * 60)

    print(f"Weights : {best_model['weights']}")
    print(f"MAPE    : {best_model['MAPE']}")
    print(f"RMSE    : {best_model['RMSE']}")

    # =====================================================
    # Save Forecast Plot
    # =====================================================

    print("\n========== Saving Forecast Plot ==========")

    prophet_plot = prophet_model.predict(
        test_df[["ds"]]
    )

    save_forecast_plot(
        test_df,
        prophet_plot
    )

    # =====================================================
    # Future Forecast
    # =====================================================

    print("\n========== Future Forecast ==========")

    result = predict(6)

    for item in result["forecast"]:
        print(item)

    # =====================================================
    # Pipeline Summary
    # =====================================================

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 60)

    print("\nMODEL COMPARISON")
    print("-" * 40)

    print(f"Prophet RMSE : {prophet_metrics['RMSE']}")
    print(f"XGBoost RMSE : {xgb_metrics['RMSE']}")
    print(f"Best Ensemble RMSE : {best_model['RMSE']}")

    if best_model["RMSE"] < xgb_metrics["RMSE"]:
        print("\n Ensemble outperformed XGBoost.")
    else:
        print("\n XGBoost outperformed Ensemble.")

    print("=" * 60)

    # =====================================================
    # End Main MLflow Run
    # =====================================================

    end_run()


if __name__ == "__main__":
    main()