"""
Train Iris classifier.

Workflow:

1. Load data
2. Train model
3. Save standalone model for BentoML
4. Evaluate model
5. Log metrics to MLflow
6. Link MLflow run to DVC dataset version
7. Register model
8. Assign staging alias
9. Run quality gate
10. Request governance approval
11. Promote only if governance approval exists

Production promotion is blocked when governance approval
has not been granted for the exact model version.
"""

from pathlib import Path

import joblib
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
from src.dvc_utils import get_dvc_data_metadata

from src.mlflow_utils import (
    set_experiment,
    start_run,
    log_params,
    log_metrics,
    log_model,
    log_artifact,
    set_tags,
    assign_staging,
    promote_model,
)

from src.governance import governance_manager


def train():
    set_experiment(EXPERIMENT_NAME)

    X_train, X_test, y_train, y_test = load_data()

    with start_run("RandomForest_Training"):

        # ---------------------------------------------------------
        # DVC DATA VERSION
        # ---------------------------------------------------------
        # Read the DVC metadata for the reference training dataset.
        # The hash uniquely identifies the dataset contents tracked
        # by DVC.
        dvc_metadata = get_dvc_data_metadata()

        print("\nDVC dataset version:")
        print(f"  Dataset : {dvc_metadata['dvc_data_path']}")
        print(f"  Hash    : {dvc_metadata['dvc_data_hash']}")

        # ---------------------------------------------------------
        # MODEL TRAINING
        # ---------------------------------------------------------
        model = RandomForestClassifier(
            n_estimators=N_ESTIMATORS,
            max_depth=MAX_DEPTH,
            random_state=RANDOM_STATE,
        )

        model.fit(X_train, y_train)

        # ---------------------------------------------------------
        # SAVE STANDALONE MODEL FOR BENTOML
        # ---------------------------------------------------------
        model_dir = Path("models")
        model_dir.mkdir(parents=True, exist_ok=True)

        model_path = model_dir / "model.pkl"

        joblib.dump(model, model_path)

        print(
            f"\nStandalone BentoML model saved to: "
            f"{model_path}"
        )

        # ---------------------------------------------------------
        # EVALUATION
        # ---------------------------------------------------------
        accuracy, precision, recall, f1 = evaluate(
            model,
            X_test,
            y_test,
        )

        # ---------------------------------------------------------
        # MLflow PARAMETERS
        # ---------------------------------------------------------
        log_params(
            {
                "algorithm": "RandomForestClassifier",
                "n_estimators": N_ESTIMATORS,
                "max_depth": MAX_DEPTH,
                "random_state": RANDOM_STATE,
            }
        )

        # ---------------------------------------------------------
        # MLflow METRICS
        # ---------------------------------------------------------
        log_metrics(
            {
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
            }
        )

        # ---------------------------------------------------------
        # MLflow TAGS
        # ---------------------------------------------------------
        set_tags(
            {
                "project": "iris_reference",
                "framework": "scikit-learn",
                "workflow": "staging_to_production",

                # BentoML traceability
                "bentoml_model_path": str(model_path),

                # DVC traceability
                "dvc_data_path": dvc_metadata[
                    "dvc_data_path"
                ],
                "dvc_data_hash": dvc_metadata[
                    "dvc_data_hash"
                ],
                "dvc_metadata_file": dvc_metadata[
                    "dvc_metadata_file"
                ],
                "dvc_pipeline": "dvc.yaml",
            }
        )

        # ---------------------------------------------------------
        # LOG DVC METADATA AS MLflow ARTIFACTS
        # ---------------------------------------------------------
        dvc_metadata_file = Path(
            dvc_metadata["dvc_metadata_file"]
        )

        if dvc_metadata_file.exists():
            log_artifact(
                str(dvc_metadata_file)
            )

        dvc_lock_file = Path("dvc.lock")

        if dvc_lock_file.exists():
            log_artifact(
                str(dvc_lock_file)
            )

        # ---------------------------------------------------------
        # REGISTER MODEL IN MLflow
        # ---------------------------------------------------------
        model_info = log_model(
            model=model,
            artifact_path="model",
            registered_model_name=MODEL_NAME,
        )

        # ---------------------------------------------------------
        # ASSIGN STAGING
        # ---------------------------------------------------------
        staging_version = assign_staging(MODEL_NAME)
        staging_version = str(staging_version)

        production_version = None

        # ---------------------------------------------------------
        # QUALITY GATE
        # ---------------------------------------------------------
        if should_promote(accuracy):

            print(
                "\nModel passed the quality gate "
                f"(accuracy={accuracy:.4f} >= "
                f"{PROMOTION_ACCURACY_THRESHOLD:.2f})"
            )

            # -----------------------------------------------------
            # GOVERNANCE APPROVAL REQUEST
            # -----------------------------------------------------
            governance_request = (
                governance_manager.request_approval(
                    model_name=MODEL_NAME,
                    model_version=staging_version,
                    requested_by=PROMOTED_BY,
                    reason=(
                        "Model passed the quality gate "
                        f"with accuracy={accuracy:.4f}"
                    ),
                )
            )

            print("\nGovernance approval required")

            print(
                f"Model Version    : "
                f"{governance_request.model_version}"
            )

            print(
                f"Governance Status: "
                f"{governance_request.status}"
            )

            # -----------------------------------------------------
            # GOVERNANCE APPROVAL CHECK
            # -----------------------------------------------------
            if governance_manager.is_approved(
                model_name=MODEL_NAME,
                model_version=staging_version,
            ):

                production_version = promote_model(
                    model_name=MODEL_NAME,
                    from_alias="staging",
                    to_alias="production",
                    expected_version=staging_version,
                )

            else:

                set_tags(
                    {
                        "governance_status": (
                            governance_request.status
                        )
                    }
                )

                print(
                    "\nProduction promotion is waiting "
                    "for governance approval."
                )

                print(
                    f"  Approve : python -m src.approve_model "
                    f"{MODEL_NAME} "
                    f"{staging_version} "
                    f"<approver_name> "
                    f'"<reason>"'
                )

                print(
                    f"  Promote : python -m "
                    f"src.promote_approved_model "
                    f"{MODEL_NAME} "
                    f"{staging_version}"
                )

        else:

            print(
                "\nModel remains in STAGING "
                f"(accuracy={accuracy:.4f} < "
                f"{PROMOTION_ACCURACY_THRESHOLD:.2f})"
            )

        # ---------------------------------------------------------
        # TRAINING SUMMARY
        # ---------------------------------------------------------
        print("\n" + "=" * 60)
        print("TRAINING COMPLETED")
        print("=" * 60)

        print(f"Model Name        : {MODEL_NAME}")
        print(f"Staging Version   : {staging_version}")

        if production_version is not None:
            print(
                f"Production Version: "
                f"{production_version}"
            )
        else:
            print(
                "Production Version: "
                "Not promoted"
            )

        print(f"Accuracy          : {accuracy:.4f}")
        print(f"Precision         : {precision:.4f}")
        print(f"Recall            : {recall:.4f}")
        print(f"F1 Score          : {f1:.4f}")

        print(
            f"Model URI         : "
            f"{model_info.model_uri}"
        )

        print(
            f"Bento Model Path  : "
            f"{model_path}"
        )

        print(
            f"DVC Dataset       : "
            f"{dvc_metadata['dvc_data_path']}"
        )

        print(
            f"DVC Data Hash     : "
            f"{dvc_metadata['dvc_data_hash']}"
        )

        print("=" * 60)

        return model


if __name__ == "__main__":
    train()

