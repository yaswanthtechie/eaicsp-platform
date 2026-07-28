from sklearn.ensemble import RandomForestClassifier

from src.config import (
    MODEL_NAME,
    EXPERIMENT_NAME,
    RANDOM_STATE,
    N_ESTIMATORS,
    MAX_DEPTH,
)

from src.data import load_data
from src.evaluate import evaluate

from src.mlflow_utils import (
    set_experiment,
    start_run,
    log_params,
    log_metrics,
    log_model,
    promote_model,
)


def train():
    """
    Train, evaluate, register,
    and promote the model.
    """

    set_experiment(EXPERIMENT_NAME)

    X_train, X_test, y_train, y_test = load_data()

    with start_run("RandomForest_Training"):

        model = RandomForestClassifier(
            n_estimators=N_ESTIMATORS,
            max_depth=MAX_DEPTH,
            random_state=RANDOM_STATE,
        )

        model.fit(X_train, y_train)

        accuracy, f1 = evaluate(
            model,
            X_test,
            y_test,
        )

        log_params(
            {
                "n_estimators": N_ESTIMATORS,
                "max_depth": MAX_DEPTH,
                "random_state": RANDOM_STATE,
            }
        )

        log_metrics(
            {
                "accuracy": accuracy,
                "f1_score": f1,
            }
        )

        model_info = log_model(
            model=model,
            artifact_path="model",
            registered_model_name=MODEL_NAME,
        )

        model_version = promote_model(MODEL_NAME)

        print("=" * 60)
        print("Training Completed Successfully")
        print("=" * 60)
        print(f"Model Name      : {MODEL_NAME}")
        print(f"Model Version   : {model_version}")
        print("Alias           : @production")
        print(f"Accuracy        : {accuracy:.4f}")
        print(f"F1 Score        : {f1:.4f}")
        print(f"Model URI       : {model_info.model_uri}")
        print("=" * 60)

        return model


if __name__ == "__main__":
    train()