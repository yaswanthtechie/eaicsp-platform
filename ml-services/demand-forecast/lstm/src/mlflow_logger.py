import os
import mlflow
import mlflow.pytorch


def start_experiment(experiment_name="LSTM_7_Day_Forecasting",run_name=None):
    """
    Sets the active experiment and starts an MLflow run using a local SQLite database.
    """
    if mlflow.active_run():
        mlflow.end_run()

    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment(experiment_name)
    mlflow.start_run(run_name=run_name)


def log_params(params):
    """
    Accepts a dictionary of hyperparameters and logs them to MLflow.
    """
    if not mlflow.active_run():
        return

    if isinstance(params, dict):
        for key, value in params.items():
            mlflow.log_param(key, value)


def log_metrics(metrics, step=None):
    """
    Accepts a dictionary of metric names and values (e.g., loss, MAE, RMSE).
    """
    if not mlflow.active_run():
        return

    if isinstance(metrics, dict):
        for key, value in metrics.items():
            if value is not None:
                if step is not None:
                    mlflow.log_metric(key, float(value), step=step)
                else:
                    mlflow.log_metric(key, float(value))


def log_model(model_or_path, artifact_path="LSTM_Model"):
    """
    Logs the model checkpoint file or PyTorch model instance to MLflow.
    """
    if not mlflow.active_run():
        return

    if isinstance(model_or_path, str):
        if os.path.exists(model_or_path):
            mlflow.log_artifact(model_or_path, artifact_path=artifact_path)
    else:
        mlflow.pytorch.log_model(model_or_path, artifact_path=artifact_path)


def log_artifacts(file_paths=None):
    """
    Logs plot images or output files to MLflow.
    """
    if not mlflow.active_run():
        return

    default_paths = ["output/loss_curve.png", "output/prediction.png"]
    paths = file_paths if file_paths is not None else default_paths

    for path in paths:
        if os.path.exists(path):
            mlflow.log_artifact(path)


def end_run():
    """
    Ends the current active MLflow run.
    """
    if mlflow.active_run():
        mlflow.end_run()