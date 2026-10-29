import mlflow
import mlflow.sklearn

from .config import TEST_SIZE


EXPERIMENT_NAME = "ETA Prediction"
MODEL_NAME = "eta_pipeline"
H2_MODEL_NAME = "eta_seed_routes"


def setup_mlflow():
    """Configure the MLflow experiment."""

    mlflow.set_experiment(
        EXPERIMENT_NAME
    )


def start_run(run_name=None):
    return mlflow.start_run(run_name=run_name)


def log_parameters(model):
    """
    Log the actual trained model parameters.

    The XGBoost configuration is sourced from the trained
    pipeline rather than duplicated here. This ensures the
    parameters recorded in MLflow always match the model
    that was actually trained.
    """

    xgb_model = model["model"]

    model_params = xgb_model.get_params()

    mlflow.log_params(
        {
            "test_size": TEST_SIZE,
            "model": "XGBRegressor",
            "objective": model_params["objective"],
            "n_estimators": model_params["n_estimators"],
            "learning_rate": model_params["learning_rate"],
            "max_depth": model_params["max_depth"],
            "min_child_weight": model_params[
                "min_child_weight"
            ],
            "subsample": model_params["subsample"],
            "colsample_bytree": model_params[
                "colsample_bytree"
            ],
            "reg_alpha": model_params["reg_alpha"],
            "reg_lambda": model_params["reg_lambda"],
            "random_state": model_params["random_state"],
            "n_jobs": model_params["n_jobs"],
        }
    )
def log_h2_parameters():
    mlflow.log_params(
        {
            "model": "XGBRegressor",
            "feature_set": "h2_seed_routes",
            "feature_count": 5,
            "training_data": "olist",
            "serving_routes": "seed",
            "carrier_used_as_model_feature": False,
        }
    )

    mlflow.set_tags(
        {
            "training_data": "olist",
            "serving_routes": "seed",
            "carrier_used_as_model_feature": "false",
        }
    )

def log_metrics(results):
    """
    Log all evaluation metrics returned by evaluate_model().

    Metrics include:
        - XGBoost MAE/RMSE
        - training-median baseline MAE/RMSE
        - Olist estimated-delivery baseline MAE/RMSE
        - improvement over training-median baseline
        - improvement over Olist baseline
    """

    mlflow.log_metrics(
        {
            # -------------------------------------------------
            # XGBoost
            # -------------------------------------------------
            "mae": results["mae"],
            "rmse": results["rmse"],

            # -------------------------------------------------
            # Training-median baseline
            # -------------------------------------------------
            "baseline_mae": results[
                "baseline_mae"
            ],
            "baseline_rmse": results[
                "baseline_rmse"
            ],

            # -------------------------------------------------
            # XGBoost improvement over training median
            # -------------------------------------------------
            "mae_improvement": results[
                "mae_improvement"
            ],
            "rmse_improvement": results[
                "rmse_improvement"
            ],

            # -------------------------------------------------
            # Olist estimated-delivery baseline
            # -------------------------------------------------
            "olist_baseline_mae": results[
                "olist_baseline_mae"
            ],
            "olist_baseline_rmse": results[
                "olist_baseline_rmse"
            ],

            # -------------------------------------------------
            # XGBoost improvement over Olist baseline
            # -------------------------------------------------
            "olist_mae_improvement": results[
                "olist_mae_improvement"
            ],
            "olist_rmse_improvement": results[
                "olist_rmse_improvement"
            ],
            "interval_coverage": results[
                "interval_coverage"
            ],
        }
    )
def log_h2_metrics(results):
    """Log H2 ETA evaluation metrics."""
    mlflow.log_metrics(
        {
            "mae": results["mae"],
            "interval_coverage": results["interval_coverage"],
        }
    )

def log_dataset_metadata(
    features,
    train,
    test,
    split_timestamp,
):
    """Log dataset and chronological split metadata."""

    mlflow.log_params(
        {
            "total_rows": len(features),
            "train_rows": len(train),
            "test_rows": len(test),
            "training_start": str(
                train[
                    "order_purchase_timestamp"
                ].min()
            ),
            "training_end": str(
                train[
                    "order_purchase_timestamp"
                ].max()
            ),
            "test_start": str(
                test[
                    "order_purchase_timestamp"
                ].min()
            ),
            "test_end": str(
                test[
                    "order_purchase_timestamp"
                ].max()
            ),
            "split_timestamp": str(
                split_timestamp
            ),
        }
    )


def log_calibration_metadata(
    calibration,
):
    """
    Log prediction interval calibration metadata.

    The calibration values are generated from
    out-of-sample residuals on the training portion.
    """

    params = {
        "prediction_interval_method": str(
            calibration["method"]
        ),
        "prediction_interval_coverage": str(
            calibration["coverage"]
        ),
        "calibration_fraction": str(
            calibration["calibration_fraction"]
        ),
        "calibration_rows": str(
            calibration["calibration_rows"]
        ),
    }

    # Quantile metadata is available for the production
    # calibration artifact, but not required for the
    # inherited comparison model.
    if "lower_quantile" in calibration:
        params["lower_quantile"] = str(
            calibration["lower_quantile"]
        )

    if "upper_quantile" in calibration:
        params["upper_quantile"] = str(
            calibration["upper_quantile"]
        )

    mlflow.log_params(params)

    mlflow.log_metrics(
        {
            "residual_lower": float(
                calibration["residual_lower"]
            ),
            "residual_upper": float(
                calibration["residual_upper"]
            ),
        }
    )

def log_model(model):
    """
    Log the trained ETA pipeline to MLflow.

    The production joblib artifact created by train_model()
    remains unchanged. MLflow stores its own tracked copy.
    """

    model_info = mlflow.sklearn.log_model(
        sk_model=model,
        name=MODEL_NAME,
        serialization_format=(
            mlflow.sklearn.SERIALIZATION_FORMAT_CLOUDPICKLE
        ),
    )

    return model_info
def log_h2_model(model, input_example):
    """Log and register the H2 seed-route ETA model with a signature."""

    from mlflow.models import infer_signature

    prediction_example = model.predict(input_example)

    signature = infer_signature(
        input_example,
        prediction_example,
    )

    model_info = mlflow.sklearn.log_model(
        sk_model=model,
        name=H2_MODEL_NAME,
        serialization_format=mlflow.sklearn.SERIALIZATION_FORMAT_CLOUDPICKLE,
        signature=signature,
        input_example=input_example,
        registered_model_name=H2_MODEL_NAME,
    )

    return model_info
