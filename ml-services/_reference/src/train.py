"""
Train Iris classifier.

Workflow:

1. Load data
2. Train model
3. Evaluate model
4. Log metrics to MLflow
5. Register model
6. Assign staging alias
7. Promote to production only if quality gate passes
"""

from sklearn.ensemble import RandomForestClassifier

from src.config import (
    MODEL_NAME,
    EXPERIMENT_NAME,
    RANDOM_STATE,
    N_ESTIMATORS,
    MAX_DEPTH,
    PROMOTION_ACCURACY_THRESHOLD,
    PROMOTED_BY,
    should_promote,
)

from src.data import load_data
from src.evaluate import evaluate

from src.mlflow_utils import (
    set_experiment,
    start_run,
    log_params,
    log_metrics,
    log_model,
    set_tags,
    assign_staging,
    promote_model,
)


def train():
    """
    Complete training pipeline.
    """

    set_experiment(EXPERIMENT_NAME)

    X_train, X_test, y_train, y_test = load_data()

    with start_run("RandomForest_Training"):

        model = RandomForestClassifier(
            n_estimators=N_ESTIMATORS,
            max_depth=MAX_DEPTH,
            random_state=RANDOM_STATE,
        )

        model.fit(
            X_train,
            y_train,
        )

        accuracy, precision, recall, f1 = evaluate(
            model,
            X_test,
            y_test,
        )

        log_params(
            {
                "algorithm": "RandomForestClassifier",
                "n_estimators": N_ESTIMATORS,
                "max_depth": MAX_DEPTH,
                "random_state": RANDOM_STATE,
            }
        )

        log_metrics(
            {
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
            }
        )

        set_tags(
            {
                "project": "iris_reference",
                "framework": "scikit-learn",
                "workflow": "staging_to_production",
            }
        )

        model_info = log_model(
            model=model,
            artifact_path="model",
            registered_model_name=MODEL_NAME,
        )

        # Assign latest registered model to staging
        staging_version = assign_staging(MODEL_NAME)

        # Promote only if the model meets the quality gate
        production_version = None

        if should_promote(accuracy):

            production_version = promote_model(
                model_name=MODEL_NAME,
                from_alias="staging",
                to_alias="production",
            )

            print(
                f"\nModel passed the promotion gate "
                f"(accuracy={accuracy:.4f} >= "
                f"{PROMOTION_ACCURACY_THRESHOLD:.2f})"
            )

        else:

            print(
                f"\nModel remains in STAGING "
                f"(accuracy={accuracy:.4f} < "
                f"{PROMOTION_ACCURACY_THRESHOLD:.2f})"
            )

        print("\n" + "=" * 60)
        print("TRAINING COMPLETED SUCCESSFULLY")
        print("=" * 60)

        print(f"Model Name : {MODEL_NAME}")
        print(f"Staging Version : {staging_version}")

        if production_version is not None:
            print(f"Production Version : {production_version}")
        else:
            print("Production Version : Not promoted")

        print(f"Accuracy : {accuracy:.4f}")
        print(f"Precision : {precision:.4f}")
        print(f"Recall : {recall:.4f}")
        print(f"F1 Score : {f1:.4f}")
        print(f"Model URI : {model_info.model_uri}")

        print("=" * 60)

        return model


if __name__ == "__main__":
    train()