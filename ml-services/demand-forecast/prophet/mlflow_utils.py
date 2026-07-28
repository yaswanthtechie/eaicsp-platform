import mlflow
import mlflow.prophet
import mlflow.xgboost


def start_experiment(experiment_name):
    mlflow.set_experiment(experiment_name)


def start_run(run_name):
    mlflow.start_run(run_name=run_name)


def log_params(params):
    mlflow.log_params(params)


def log_metrics(metrics):
    mlflow.log_metrics(metrics)


def log_model(model, model_name):
    """
    Log Prophet and XGBoost models using their respective MLflow flavors.
    """

    if "prophet" in model_name.lower():
        mlflow.prophet.log_model(
            model,
            name=model_name
        )

    elif "xgboost" in model_name.lower():
        mlflow.xgboost.log_model(
            model,
            name=model_name
        )


def end_run():
    mlflow.end_run()