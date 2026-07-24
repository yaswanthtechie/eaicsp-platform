import mlflow
import mlflow.sklearn

from sklearn.ensemble import RandomForestClassifier

from src.data import load_data
from src.evaluate import evaluate
from src.config import *

# Set MLflow tracking directory
mlflow.set_tracking_uri("file:./mlruns")


def train():
    mlflow.set_experiment(EXPERIMENT_NAME)

    X_train, X_test, y_train, y_test = load_data()

    with mlflow.start_run():

        model = RandomForestClassifier(
            n_estimators=N_ESTIMATORS,
            max_depth=MAX_DEPTH,
            random_state=RANDOM_STATE,
        )

        model.fit(X_train, y_train)

        accuracy, f1 = evaluate(model, X_test, y_test)

        mlflow.log_param("n_estimators", N_ESTIMATORS)
        mlflow.log_param("max_depth", MAX_DEPTH)

        mlflow.log_metric("accuracy", accuracy)
        mlflow.log_metric("f1_score", f1)

        model_info = mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path="model",
            registered_model_name=MODEL_NAME,
        )

        print("=" * 50)
        print("Model URI :", model_info.model_uri)
        print("Accuracy  :", accuracy)
        print("F1 Score  :", f1)
        print("=" * 50)


if __name__ == "__main__":
    train()