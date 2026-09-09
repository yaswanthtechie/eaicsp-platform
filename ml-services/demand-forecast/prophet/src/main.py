import os
import json

import pandas as pd
import mlflow
from src.scenario_forecasting import (
    create_promotion_scenario,
    compare_scenarios
)
from src.accuracy_monitor import (
    monitor_forecast_accuracy
)


from src.data import load_sales_data
from src.external_regressors import (
    add_external_regressors,
    validate_external_regressors,
)


from src.train_prophet import (
    train_prophet,
    predict_prophet
)


from src.train_xgboost import (
    train_xgboost,
    predict_xgboost
)


from src.evaluate import evaluate


from src.predict import predict


from src.ensemble import (
    weighted_ensemble,
    ensemble_interval
)


from src.plot import save_forecast_plot


from src.mlflow_utils import (
    start_experiment,
    start_run,
    log_params,
    log_metrics,
    log_model,
    end_run
)



def main():


    print("=" * 60)
    print("Demand Forecasting Pipeline Started")
    print("=" * 60)



    # ===============================
    # Load Dataset
    # ===============================

    df = load_sales_data()

    df = add_external_regressors(df)

    validate_external_regressors(df)

    print(
        "External regressors added successfully."
    )

    print(
        f"Total Rows : {len(df)}"
    )



    # ===============================
    # Prepare Prophet Data
    # ===============================


    prophet_df = df.rename(
        columns={
            "date":"ds",
            "quantity_sold":"y"
        }
    )


    prophet_df["ds"] = pd.to_datetime(
        prophet_df["ds"]
    )



    # ===============================
    # Train Test Split
    # ===============================


    train_df = prophet_df[
        prophet_df["ds"] < "2015-01-01"
    ].copy()


    test_df = prophet_df[
        prophet_df["ds"] >= "2015-01-01"
    ].copy()



    print(
        f"Training Rows : {len(train_df)}"
    )


    print(
        f"Testing Rows : {len(test_df)}"
    )



    # ===============================
    # MLflow
    # ===============================


    start_experiment(
        "Forecasting Project"
    )


    start_run(
        "Demand_Forecasting"
    )



    common_params = {


        "train_rows": len(train_df),


        "test_rows": len(test_df),


        "prophet_yearly": True,


        "xgb_estimators":300,


        "xgb_learning_rate":0.03,


        "xgb_max_depth":5

    }


    log_params(
        common_params
    )



    # ===============================
    # Train Prophet
    # ===============================


    print(
        "\n========== Training Prophet =========="
    )


    prophet_model = train_prophet(
        train_df
    )


    print(
        "Prophet trained successfully"
    )



    # ===============================
    # Train XGBoost
    # ===============================


    print(
        "\n========== Training XGBoost =========="
    )


    xgb_result = train_xgboost(
        prophet_df
    )


    xgb_model = xgb_result["model"]


    print(
        "XGBoost trained successfully"
    )



    # ===============================
    # Save MLflow Models
    # ===============================


    log_model(
        prophet_model,
        "Prophet_Model"
    )


    log_model(
        xgb_model,
        "XGBoost_Model"
    )
        # ===============================
    # Predictions
    # ===============================

    print(
        "\n========== Predictions =========="
    )


    # Prophet Test Prediction

    prophet_forecast = predict_prophet(
        prophet_model,
        test_df
    )


    # XGBoost Test Prediction

    xgb_predictions, xgb_forecast = predict_xgboost(
        xgb_result,
        prophet_df
    )



    # ===============================
    # Merge Predictions by Date
    # ===============================

    merged_forecast = prophet_forecast.merge(
        xgb_forecast,
        on="ds",
        how="inner"
    )


    actual = merged_forecast["y"].values



    print(
        "Evaluation Samples:",
        len(merged_forecast)
    )


    print(
        "Prophet Samples:",
        len(prophet_forecast)
    )


    print(
        "XGBoost Samples:",
        len(xgb_forecast)
    )



    # ===============================
    # Prophet Evaluation
    # ===============================


    print(
        "\n========== Prophet Evaluation =========="
    )


    prophet_metrics = evaluate(
        actual,
        merged_forecast["yhat"].values
    )


    print(
        prophet_metrics
    )



    # ===============================
    # XGBoost Evaluation
    # ===============================


    print(
        "\n========== XGBoost Evaluation =========="
    )


    xgb_metrics = evaluate(
        actual,
        merged_forecast["prediction"].values
    )


    print(
        xgb_metrics
    )



    # ===============================
    # Ensemble Evaluation
    # ===============================


    print(
        "\n========== Ensemble Evaluation =========="
    )


    ensemble_results = []



    weight_combinations = [
    (0.0, 1.0),
    (0.1, 0.9),
    (0.2, 0.8),
    (0.3, 0.7),
    (0.4, 0.6),
    (0.5, 0.5),
    (0.6, 0.4),
    (0.7, 0.3),
    (0.8, 0.2),
    (0.9, 0.1),
    (1.0, 0.0),
]



    for prophet_weight, xgb_weight in weight_combinations:



        run_name = (

            f"Ensemble_"
            f"{int(prophet_weight*100)}_"
            f"{int(xgb_weight*100)}"

        )



        with mlflow.start_run(
            run_name=run_name,
            nested=True
        ):



            print(
                f"\nTesting weights {prophet_weight}/{xgb_weight}"
            )



            log_params({

                "prophet_weight":
                    prophet_weight,


                "xgb_weight":
                    xgb_weight

            })



            # Ensemble prediction

            ensemble_prediction = weighted_ensemble(

                merged_forecast["yhat"].values,


                merged_forecast["prediction"].values,


                prophet_weight=prophet_weight,


                xgb_weight=xgb_weight

            )



            ensemble_metrics = evaluate(

                actual,


                ensemble_prediction

            )



            print(
                ensemble_metrics
            )



            log_metrics({

                "prophet_rmse":
                    prophet_metrics["RMSE"],


                "xgb_rmse":
                    xgb_metrics["RMSE"],


                "ensemble_rmse":
                    ensemble_metrics["RMSE"],


                "prophet_mape":
                    prophet_metrics["MAPE"],


                "xgb_mape":
                    xgb_metrics["MAPE"],


                "ensemble_mape":
                    ensemble_metrics["MAPE"]

            })



            # Prediction Interval

            ensemble_lower, ensemble_upper = ensemble_interval(

                merged_forecast["yhat_lower"].values,


                merged_forecast["yhat_upper"].values,


                merged_forecast["lower"].values,


                merged_forecast["upper"].values,


                prophet_weight=prophet_weight,


                xgb_weight=xgb_weight

            )



            ensemble_results.append({

                "weights":
                    f"{prophet_weight}-{xgb_weight}",


                "MAPE":
                    ensemble_metrics["MAPE"],


                "RMSE":
                    ensemble_metrics["RMSE"],


                "prediction":
                    ensemble_prediction,


                "lower":
                    ensemble_lower,


                "upper":
                    ensemble_upper

            })



    # ===============================
    # Select Best Ensemble
    # ===============================


    best_model = min(

        ensemble_results,

        key=lambda x:x["RMSE"]

    )



    weights = best_model["weights"].split("-")



    best_weights = {


        "prophet_weight":
            float(weights[0]),


        "xgb_weight":
            float(weights[1])

    }
    log_model(
        best_weights,
        "Best_Ensemble"
    )



    os.makedirs(

        "models",

        exist_ok=True

    )



    with open(

        "models/best_weights.json",

        "w"

    ) as f:


        json.dump(

            best_weights,

            f,

            indent=4

        )



    print(
        "\nBest weights saved"
    )


    print(
        best_weights
    )
    # ===============================
    # Forecast Accuracy Monitoring
    # ===============================

    print(
        "\n========== FORECAST ACCURACY MONITORING =========="
    )

    monitoring_df = pd.DataFrame({

        "date":
            merged_forecast["ds"].values,

        "actual":
            actual,

        "predicted":
            best_model["prediction"]

    })


    monitoring_result = monitor_forecast_accuracy(

        monitoring_df,

        window=3,

        threshold=10.0

    )


    print(
        "\n========== OVERALL MONITORING METRICS =========="
    )

    print(
        f"Overall MAPE: "
        f"{monitoring_result['overall_mape']:.2f}%"
    )


    print(
        f"Latest Rolling MAPE: "
        f"{monitoring_result['latest_rolling_mape']:.2f}%"
    )


    print(
        "\n========== ALERT STATUS =========="
    )

    print(
        monitoring_result["alert_message"]
    )
    # ===============================
    # Scenario / What-if Forecasting
    # ===============================

    print(
        "\n========== SCENARIO FORECASTING =========="
    )


    # Baseline future dataframe

    scenario_input = test_df[
        [
            "ds",
            "is_holiday",
            "promotion",
            "weather_index"
        ]
    ].copy()


    # -------------------------------
    # Baseline Forecast
    # -------------------------------

    baseline_forecast = prophet_model.predict(
        scenario_input
    )


    # -------------------------------
    # Create Promotion Scenario
    # -------------------------------

    promotion_scenario_input = (
        create_promotion_scenario(

            scenario_input,

            promotion_increase=0.20,

            scenario_month=12

        )
    )


    # -------------------------------
    # Scenario Forecast
    # -------------------------------

    scenario_forecast = prophet_model.predict(
        promotion_scenario_input
    )


    # -------------------------------
    # Compare Forecasts
    # -------------------------------

    scenario_comparison = compare_scenarios(

        baseline_forecast,

        scenario_forecast

    )


    print(
        "\n========== BASELINE VS PROMOTION SCENARIO =========="
    )


    print(
        scenario_comparison[
            [
                "date",
                "baseline_forecast",
                "scenario_forecast",
                "forecast_difference",
                "percentage_change"
            ]
        ]
    )


    print(
        "\n========== SCENARIO SUMMARY =========="
    )


    total_baseline = (
        scenario_comparison[
            "baseline_forecast"
        ].sum()
    )


    total_scenario = (
        scenario_comparison[
            "scenario_forecast"
        ].sum()
    )


    total_difference = (
        total_scenario
        -
        total_baseline
    )


    print(
        f"Baseline Forecast Total: "
        f"{total_baseline:.2f}"
    )


    print(
        f"Scenario Forecast Total: "
        f"{total_scenario:.2f}"
    )


    print(
        f"Forecast Difference: "
        f"{total_difference:.2f}"
    )
    # ===============================
    # Save Forecast Plot
    # ===============================

    print(
        "\n========== Saving Forecast Plot =========="
    )


    prophet_plot = prophet_model.predict(
        test_df[
            [
                "ds",
                "is_holiday",
                "promotion",
                "weather_index",
            ]
        ]
    )


    save_forecast_plot(
        test_df,
        prophet_plot
    )



    # ===============================
    # Future Forecast
    # ===============================

    print(
        "\n========== Future Forecast =========="
    )


    result = predict(6)


    for item in result["forecast"]:

        print(item)



    # ===============================
    # Pipeline Summary
    # ===============================


    print(
        "\n" + "=" * 60
    )

    print(
        "PIPELINE COMPLETED SUCCESSFULLY"
    )

    print(
        "=" * 60
    )



    print(
        "\nMODEL COMPARISON"
    )

    print(
        "-" * 40
    )



    print(
        f"Prophet RMSE : {prophet_metrics['RMSE']}"
    )


    print(
        f"XGBoost RMSE : {xgb_metrics['RMSE']}"
    )


    print(
        f"Best Ensemble RMSE : {best_model['RMSE']}"
    )



    print(
        "\nBEST ENSEMBLE WEIGHTS"
    )


    print(
        best_weights
    )



    if best_model["RMSE"] < xgb_metrics["RMSE"]:


        print(
            "\nEnsemble outperformed XGBoost."
        )


    else:


        print(
            "\nXGBoost outperformed Ensemble."
        )



    print(
        "=" * 60
    )



    # ===============================
    # End MLflow Run
    # ===============================


    end_run()



if __name__ == "__main__":

    main()