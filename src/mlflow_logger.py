import mlflow
import mlflow.pytorch

def start_experiment():

    mlflow.set_experiment("LSTM_7_Day_Forecasting")

    mlflow.start_run()


def log_params(epochs,
               lr,
               hidden_size,
               batch_size):

    mlflow.log_param("epochs", epochs)
    mlflow.log_param("learning_rate", lr)
    mlflow.log_param("hidden_size", hidden_size)
    mlflow.log_param("batch_size", batch_size)


def log_metrics(loss,
                mae,
                rmse,
                mape):

    mlflow.log_metric("Loss", loss)
    mlflow.log_metric("MAE", mae)
    mlflow.log_metric("RMSE", rmse)
    mlflow.log_metric("MAPE", mape)


def log_model(model):

    mlflow.pytorch.log_model(
        model,
        artifact_path="LSTM_Model"
    )


def log_artifacts():

    mlflow.log_artifact(
        "output/loss_curve.png"
    )

    mlflow.log_artifact(
        "output/prediction.png"
    )


def end_run():

    mlflow.end_run()