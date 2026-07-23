import mlflow
import mlflow.sklearn


def start_experiment(experiment_name):
    """
    Create or select an MLflow experiment.
    """
    mlflow.set_experiment(experiment_name)


def start_run(run_name):
    """
    Start a new MLflow run.
    """
    mlflow.start_run(run_name=run_name)


def log_params(params):
    """
    Log parameters.
    """
    mlflow.log_params(params)


def log_metrics(metrics):
    """
    Log metrics.
    """
    mlflow.log_metrics(metrics)


def log_model(model, model_name):
    """
    Save model into MLflow.
    """
    mlflow.sklearn.log_model(model, model_name)


def end_run():
    """
    Finish current run.
    """
    mlflow.end_run()