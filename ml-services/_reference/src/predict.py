import mlflow.sklearn


MODEL_URI = "models:/iris_classifier/latest"


def load_model():
    """
    Load MLflow sklearn model
    """
    model = mlflow.sklearn.load_model(MODEL_URI)
    return model