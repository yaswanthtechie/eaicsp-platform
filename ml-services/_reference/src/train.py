"""
Train Iris classifier.

Workflow:

1. Load data from the DVC-tracked processed.csv
2. Train model
3. Save standalone model for BentoML
4. Evaluate model
5. Log metrics to MLflow
6. Link MLflow run to exact DVC data version
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

from src.dvc_utils import (
    get_training_data_version,
)

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

from src.governance import (
    governance_manager,
)


def train():

    set_experiment(
        EXPERIMENT_NAME
    )

    # ---------------------------------------------------------
    # LOAD DVC-TRACKED TRAINING DATA
    # ---------------------------------------------------------
    #
    # load_data() now reads:
    #
    # data/reference/processed.csv
    #
    # This means the model is trained on the exact data
    # produced by the DVC pipeline.
    #
    X_train, X_test, y_train, y_test = load_data()

    with start_run(
        "RandomForest_Training"
    ):

        # -----------------------------------------------------
        # DVC DATA VERSION
        # -----------------------------------------------------
        #
        # Record the MD5 of the exact file load_data() reads.
        # Also compare it with the MD5 recorded by dvc.lock.
        #
        data_version = (
            get_training_data_version()
        )

        print(
            "\nTraining data version:"
        )

        print(
            "  Dataset          : "
            f"{data_version['training_data_path']}"
        )

        print(
            "  MD5              : "
            f"{data_version['training_data_md5']}"
        )

        print(
            "  Matches dvc.lock : "
            f"{data_version['matches_dvc_lock']}"
        )

        # -----------------------------------------------------
        # MODEL TRAINING
        # -----------------------------------------------------

        model = RandomForestClassifier(
            n_estimators=N_ESTIMATORS,
            max_depth=MAX_DEPTH,
            random_state=RANDOM_STATE,
        )

        model.fit(
            X_train,
            y_train,
        )

        # -----------------------------------------------------
        # SAVE STANDALONE MODEL FOR BENTOML
        # -----------------------------------------------------

        model_dir = Path(
            "models"
        )

        model_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        model_path = (
            model_dir
            / "model.pkl"
        )

        joblib.dump(
            model,
            model_path,
        )

        print(
            "\nStandalone BentoML model saved to: "
            f"{model_path}"
        )

        # -----------------------------------------------------
        # EVALUATION
        # -----------------------------------------------------

        accuracy, precision, recall, f1 = evaluate(
            model,
            X_test,
            y_test,
        )

        # -----------------------------------------------------
        # MLflow PARAMETERS
        # -----------------------------------------------------

        log_params(
            {
                "algorithm": (
                    "RandomForestClassifier"
                ),
                "n_estimators": (
                    N_ESTIMATORS
                ),
                "max_depth": (
                    MAX_DEPTH
                ),
                "random_state": (
                    RANDOM_STATE
                ),
            }
        )

        # -----------------------------------------------------
        # MLflow METRICS
        # -----------------------------------------------------

        log_metrics(
            {
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
            }
        )

        # -----------------------------------------------------
        # MLflow TAGS
        # -----------------------------------------------------

        set_tags(
            {
                "project": "iris_reference",
                "framework": "scikit-learn",
                "workflow": (
                    "staging_to_production"
                ),

                # BentoML traceability
                "bentoml_model_path": str(
                    model_path
                ),

                # DVC traceability:
                # exact data file used for training
                **data_version,

                "dvc_pipeline": "dvc.yaml",
            }
        )

        # -----------------------------------------------------
        # LOG DVC LOCK AS MLflow ARTIFACT
        # -----------------------------------------------------

        dvc_lock_file = Path(
            "dvc.lock"
        )

        if dvc_lock_file.exists():
            log_artifact(
                str(dvc_lock_file)
            )

        # -----------------------------------------------------
        # REGISTER MODEL IN MLflow
        # -----------------------------------------------------

        model_info = log_model(
            model=model,
            artifact_path="model",
            registered_model_name=MODEL_NAME,
        )

        # -----------------------------------------------------
        # ASSIGN STAGING
        # -----------------------------------------------------

        staging_version = assign_staging(
            MODEL_NAME
        )

        staging_version = str(
            staging_version
        )

        production_version = None

        # -----------------------------------------------------
        # QUALITY GATE
        # -----------------------------------------------------

        if should_promote(
            accuracy
        ):

            print(
                "\nModel passed the quality gate "
                f"(accuracy={accuracy:.4f} >= "
                f"{PROMOTION_ACCURACY_THRESHOLD:.2f})"
            )

            # -------------------------------------------------
            # GOVERNANCE APPROVAL REQUEST
            # -------------------------------------------------

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

            print(
                "\nGovernance approval required"
            )

            print(
                "Model Version    : "
                f"{governance_request.model_version}"
            )

            print(
                "Governance Status: "
                f"{governance_request.status}"
            )

            # -------------------------------------------------
            # GOVERNANCE APPROVAL CHECK
            # -------------------------------------------------

            if governance_manager.is_approved(
                model_name=MODEL_NAME,
                model_version=staging_version,
            ):

                production_version = (
                    promote_model(
                        model_name=MODEL_NAME,
                        from_alias="staging",
                        to_alias="production",
                        expected_version=staging_version,
                    )
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
                    f"  Approve : python -m "
                    f"src.approve_model "
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

        # -----------------------------------------------------
        # TRAINING SUMMARY
        # -----------------------------------------------------

        print(
            "\n" + "=" * 60
        )

        print(
            "TRAINING COMPLETED"
        )

        print(
            "=" * 60
        )

        print(
            f"Model Name        : {MODEL_NAME}"
        )

        print(
            f"Staging Version   : "
            f"{staging_version}"
        )

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

        print(
            f"Accuracy          : "
            f"{accuracy:.4f}"
        )

        print(
            f"Precision         : "
            f"{precision:.4f}"
        )

        print(
            f"Recall            : "
            f"{recall:.4f}"
        )

        print(
            f"F1 Score          : "
            f"{f1:.4f}"
        )

        print(
            f"Model URI         : "
            f"{model_info.model_uri}"
        )

        print(
            f"Bento Model Path  : "
            f"{model_path}"
        )

        print(
            f"Training Data     : "
            f"{data_version['training_data_path']}"
        )

        print(
            f"Training Data MD5 : "
            f"{data_version['training_data_md5']} "
            f"(matches dvc.lock: "
            f"{data_version['matches_dvc_lock']})"
        )

        print(
            "=" * 60
        )

        return model


if __name__ == "__main__":
    train()