# # from src.data import load_sales_data, validate
# # from train_prophet import train_model
# # from src.evaluate import evaluate
# # from src.predict import predict
# # from src.plot import save_forecast_plot

# # df = load_sales_data()

# # validate(df)

# # model, train, test, forecast = train_model(df)

# # print("Training Rows :", len(train))
# # print("Testing Rows  :", len(test))

# # rmse, mape = evaluate(test, forecast)
# # save_forecast_plot(test, forecast)

# # print("\nFuture Forecast")

# # result = predict(6)

# # for item in result["forecast"]:
# #     print(item)

# from src.data import load_sales_data
# from src.train_prophet import train_prophet
# from src.train_xgboost import train_xgboost
# from src.evaluate import evaluate
# from src.predict import predict
# from src.ensemble import weighted_ensemble


# def main():

#     df = load_sales_data()

#     print("Total Rows :", len(df))

#     prophet_df = df.rename(
#         columns={
#             "date": "ds",
#             "quantity_sold": "y"
#         }
#     )

#     train = prophet_df[prophet_df["ds"] < "2015-01-01"]

#     test = prophet_df[prophet_df["ds"] >= "2015-01-01"]

#     print("Training Rows :", len(train))
#     print("Testing Rows :", len(test))
from src.data import load_sales_data
from src.train_prophet import train_prophet, predict_prophet
from src.train_xgboost import train_xgboost, predict_xgboost
from src.evaluate import evaluate
from src.predict import predict
from src.ensemble import weighted_ensemble

from src.mlflow_utils import (
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
    # Start MLflow
    # -----------------------------------
    start_experiment("Forecasting Project")
    start_run("Prophet_XGBoost_Ensemble")

    # Rename columns
    prophet_df = df.rename(
        columns={
            "date": "ds",
            "quantity_sold": "y"
        }
    )

    # -----------------------------------
    # Time-based Split
    # -----------------------------------
    train = prophet_df[prophet_df["ds"] < "2015-01-01"]
    test = prophet_df[prophet_df["ds"] >= "2015-01-01"]

    print("Training Rows :", len(train))
    print("Testing Rows :", len(test))

    # -----------------------------------
    # Train Prophet
    # -----------------------------------
    print("\n========== Training Prophet ==========")

    prophet_model = train_prophet(train)

    print("✅ Prophet model trained successfully.")

    # -----------------------------------
    # Train XGBoost
    # -----------------------------------
    print("\n========== Training XGBoost ==========")

    xgb_model = train_xgboost(train)

    print("✅ XGBoost model trained successfully.")

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
        test
    )

    xgb_predictions = predict_xgboost(
        xgb_model,
        test
    )

    # -----------------------------------
    # Prophet Evaluation
    # -----------------------------------
    print("\n========== Prophet Evaluation ==========")

    prophet_metrics = evaluate(
        test["y"].values,
        prophet_predictions
    )

    print(prophet_metrics)

    log_metrics({
        "prophet_mape": prophet_metrics["MAPE"],
        "prophet_rmse": prophet_metrics["RMSE"]
    })

    # -----------------------------------
    # XGBoost Evaluation
    # -----------------------------------
    print("\n========== XGBoost Evaluation ==========")

    xgb_metrics = evaluate(
        test["y"].values,
        xgb_predictions
    )

    print(xgb_metrics)

    log_metrics({
        "xgb_mape": xgb_metrics["MAPE"],
        "xgb_rmse": xgb_metrics["RMSE"]
    })

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
        test["y"].values,
        ensemble_predictions
    )

    print(ensemble_metrics)

    log_metrics({
        "ensemble_mape": ensemble_metrics["MAPE"],
        "ensemble_rmse": ensemble_metrics["RMSE"]
    })

    # -----------------------------------
    # Save Models
    # -----------------------------------
    # Save only XGBoost model
    # log_model(xgb_model, "XGBoost_Model")

    # -----------------------------------
    # Future Forecast
    # -----------------------------------
    print("\n========== Future Forecast ==========")

    result = predict(6)

    for item in result["forecast"]:
        print(item)

    # -----------------------------------
    # End MLflow Run
    # -----------------------------------
    end_run()


if __name__ == "__main__":
    main()