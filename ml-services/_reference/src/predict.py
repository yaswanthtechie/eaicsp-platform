import mlflow.sklearn
from mlflow.tracking import MlflowClient

MODEL_NAME = "iris_classifier"
MODEL_URI = f"models:/{MODEL_NAME}@production"

client = MlflowClient()


def load_model():
    """
    Load the Production model from the MLflow Model Registry.
    """

    model = mlflow.sklearn.load_model(MODEL_URI)

    model_version = client.get_model_version_by_alias(
        MODEL_NAME,
        "production",
    ).version
    # print("="*50)
    # print(f"Loaded model version: {model_version}")
    # print("="*50)

    return model, model_version